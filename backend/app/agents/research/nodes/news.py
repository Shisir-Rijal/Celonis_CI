import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from app.agents.research.state import ResearchState, NewsData, NewsItem
import structlog
import httpx
import finnhub
import asyncio
import json
from firecrawl import V1FirecrawlApp as FirecrawlApp
from pydantic import BaseModel
from app.config import get_settings
from datetime import date, datetime, timezone
from app.agents.shared.utils.finnhub import _get_symbol
from app.agents.research.repositories.research_repository import insert_research_snapshot, snapshot_exists
from openai import AsyncOpenAI


settings = get_settings()
logger = structlog.get_logger(__name__)
today = date.today().strftime("%Y-%m-%d")


# --- Quelle 1: Finnhub ---

def _get_finnhub_news(ticker: str, company: str, domain: str) -> list[NewsItem]:
    client = finnhub.Client(api_key=get_settings().FINNHUB_API_KEY)
    raw = client.company_news(ticker, _from=today, to=today)

    return [
        NewsItem(
            company=company,
            url=item.get("url") or f"https://{domain}",
            title=item.get("headline"),
            source_type="finnhub",
            heading=item.get("headline"),
            summary=item.get("summary"),
            image=item.get("image"),
            published_date=today,
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


async def _get_serper_news(domain: str, company: str) -> list[NewsItem]:
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

    # scrape full text for up to 15 articles in parallel
    texts = await asyncio.gather(*[
        _scrape_article_text(item["link"], app, openai)
        for item in unique[:15]
    ])
    text_map = {item["link"]: text for item, text in zip(unique[:15], texts)}

    return [
        NewsItem(
            company=company,
            url=item.get("link") or f"https://{domain}",
            title=item.get("title"),
            source_type="serper",
            heading=item.get("title"),
            text=text_map.get(item.get("link")),
            summary=item.get("snippet"),
            image=item.get("imageUrl") if (item.get("imageUrl") or "").startswith("http") else None,
            published_date=item.get("date", today),
        )
        for item in unique
    ]


# --- Quelle 3: Firecrawl ---

async def _get_firecrawl_news(domain: str, company: str) -> list[NewsItem]:
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
                company=company,
                url=url,
                title=data.get("heading"),
                source_type="firecrawl",
                heading=data.get("heading"),
                text=data.get("text"),
                author=data.get("author"),
                published_date=data.get("date", today),
            )
        except Exception:
            return None

    scraped = await asyncio.gather(*[_scrape_article(u) for u in urls[:5]])
    return [r for r in scraped if r is not None]


async def run(state: ResearchState) -> dict:
    domain = state["competitor_domain"]
    if snapshot_exists(domain, "news"):
        logger.info("node_skipped_cached", node="news", domain=domain)
        return {"completed_nodes": ["news"]}
    company = domain.split(".")[0].capitalize()
    try:
        all_news: list[NewsItem] = []

        # Finnhub
        ticker = _get_symbol(domain)
        if ticker:
            all_news += _get_finnhub_news(ticker, company, domain)

        # Serper
        all_news += await _get_serper_news(domain, company)

        # Firecrawl
        all_news += await _get_firecrawl_news(domain, company)

        news_data = NewsData(news=all_news)
        try:
            insert_research_snapshot(domain, datetime.now(timezone.utc), "news", news_data)
        except Exception as db_err:
            logger.warning("snapshot_write_failed", node="news", error=str(db_err))
        return {
            "news": news_data,
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
