import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from app.agents.research.state import ResearchState, NewsData
import structlog
import httpx
import finnhub
import asyncio
import json
from firecrawl import V1FirecrawlApp as FirecrawlApp
from pydantic import BaseModel
from app.config import get_settings
from datetime import date
from app.agents.shared.utils.finnhub import _get_symbol
from openai import AsyncOpenAI


settings = get_settings()
logger = structlog.get_logger(__name__)
today = date.today().strftime("%Y-%m-%d")


class NewsItem(BaseModel):
    heading: str | None = None
    text: str | None = None
    image: str | None = None
    author: str | None = None
    summary: str | None = None
    source: str | None = None
    source_link: str | None = None
    date: str | None = None


# --- Quelle 1: Finnhub ---

def _get_finnhub_news(ticker: str) -> list[NewsItem]:
    client = finnhub.Client(api_key=get_settings().FINNHUB_API_KEY)
    raw = client.company_news(ticker, _from=today, to=today)

    return [
        NewsItem(
            heading=item.get("headline"),
            summary=item.get("summary"),
            source=item.get("source"),
            source_link=item.get("url"),
            image=item.get("image"),
            date=today,
        )
        for item in raw
    ]


# --- Quelle 2: SerperAPI ---

async def _scrape_article_text(url: str, app: FirecrawlApp, openai: AsyncOpenAI) -> str | None:
    try:
        scraped = await asyncio.to_thread(app.scrape_url, url, formats=["markdown"])
        md = getattr(scraped, "markdown", None)
        if not md:
            return None
        resp = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "Extract the full text of this news article — every paragraph verbatim, not a summary. "
                    'Return JSON: {"text": "...full article text..."}.'
                )},
                {"role": "user", "content": md[:10000]},
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content).get("text")
    except Exception:
        return None


async def _get_serper_news(domain: str) -> list[NewsItem]:
    company = domain.replace(".com", "").replace(".io", "")
    all_raw = []

    queries = [
        f"{company} news",
        f"{company} press release",
        f"{company} announcement",
        f"site:{domain} news",
    ]

    async with httpx.AsyncClient() as client:
        for query in queries:
            response = await client.post(
                "https://google.serper.dev/news",
                headers={"X-API-KEY": get_settings().SERPER_API_KEY},
                json={"q": query, "num": 5},
                timeout=10,
            )
            all_raw += response.json().get("news", [])

    seen: set[str] = set()
    unique = []
    for item in all_raw:
        url = item.get("link")
        if url and url not in seen:
            seen.add(url)
            unique.append(item)

    app = FirecrawlApp(api_key=get_settings().FIRECRAWL_API_KEY)
    openai = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)

    # scrape full text for up to 5 articles in parallel
    texts = await asyncio.gather(*[
        _scrape_article_text(item["link"], app, openai)
        for item in unique[:5]
    ])
    text_map = {item["link"]: text for item, text in zip(unique[:5], texts)}

    return [
        NewsItem(
            heading=item.get("title"),
            text=text_map.get(item.get("link")),
            summary=item.get("snippet"),
            source="serper",
            source_link=item.get("link"),
            image=item.get("imageUrl") if (item.get("imageUrl") or "").startswith("http") else None,
            date=item.get("date", today),
        )
        for item in unique
    ]


# --- Quelle 3: Firecrawl ---

async def _get_firecrawl_news(domain: str) -> list[NewsItem]:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": get_settings().SERPER_API_KEY},
            json={"q": f"site:{domain} newsroom OR blog OR press", "num": 1},
            timeout=10,
        )
    results = response.json().get("organic", [])
    if not results:
        return []

    app = FirecrawlApp(api_key=get_settings().FIRECRAWL_API_KEY)
    openai = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)

    # Step 1: scrape the listing page to extract individual article URLs
    listing = await asyncio.to_thread(app.scrape_url, results[0]["link"], formats=["markdown"])
    if not getattr(listing, "markdown", None):
        return []

    url_resp = await openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": (
                "Extract individual news/blog article URLs from this listing page. "
                "Return a JSON object with key 'urls' containing a list of full URLs (starting with https://). "
                "Only include URLs that link to individual articles, not category or tag pages. Max 5 URLs."
            )},
            {"role": "user", "content": listing.markdown[:4000]},
        ],
        response_format={"type": "json_object"},
    )
    urls: list[str] = json.loads(url_resp.choices[0].message.content).get("urls", [])
    if not urls:
        return []

    # Step 2: scrape each article for full text
    async def _scrape_article(url: str) -> NewsItem | None:
        try:
            scraped = await asyncio.to_thread(app.scrape_url, url, formats=["markdown"])
            md = getattr(scraped, "markdown", None)
            if not md:
                return None
            resp = await openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": (
                        "Extract this news article. Return a JSON object with fields:\n"
                        "- heading: article title\n"
                        "- text: the FULL article text — every paragraph verbatim, not a summary\n"
                        "- author: author name if present, or null\n"
                        "- date: YYYY-MM-DD if explicitly stated, null otherwise"
                    )},
                    {"role": "user", "content": md[:10000]},
                ],
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content)
            return NewsItem(
                heading=data.get("heading"),
                text=data.get("text"),
                author=data.get("author"),
                source="firecrawl",
                source_link=url,
                date=data.get("date", today),
            )
        except Exception:
            return None

    scraped = await asyncio.gather(*[_scrape_article(u) for u in urls[:5]])
    return [r for r in scraped if r is not None]


async def run(state: ResearchState) -> dict:
    domain = state["competitor_domain"]
    try:
        all_news: list[NewsItem] = []

        # Finnhub
        ticker = _get_symbol(domain)
        if ticker:
            all_news += _get_finnhub_news(ticker)

        # Serper
        all_news += await _get_serper_news(domain)

        # Firecrawl
        all_news += await _get_firecrawl_news(domain)

        return {
            "news": NewsData(news=all_news, source="finnhub+serper+firecrawl"),
            "completed_nodes": ["news"],
        }
    except Exception as e:
        logger.error("node_failed", node="news", error=str(e))
        return {"errors": [f"news: {e}"]}


if __name__ == "__main__":
    import asyncio
    structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

    async def main():
        from app.agents.research.state import VisualsData, PositioningData, FinancialData, SocialData, SeoGeoData, EventsData, NewsletterData

        state = ResearchState(
            competitor_domain="ibm.com",
            visuals=VisualsData(),
            positioning=PositioningData(),
            financials=FinancialData(),
            socials=SocialData(),
            seogeo=SeoGeoData(),
            news=NewsData(),
            events=EventsData(),
            newsletter=NewsletterData(),
            errors=[],
            completed_nodes=[],
        )
        result = await run(state)
        if result.get("errors"):
            print("Errors:", result["errors"])
        else:
            for item in result["news"].news:
                print(item.model_dump_json(indent=2))

    asyncio.run(main())
