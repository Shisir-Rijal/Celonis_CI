import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from app.agents.research.state import ResearchState, NewsData
import structlog
import httpx
import finnhub
import asyncio
import json
from firecrawl import FirecrawlApp
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

    # Duplikate entfernen anhand der URL
    seen = set()
    unique = []
    for item in all_raw:
        url = item.get("link")
        if url and url not in seen:
            seen.add(url)
            unique.append(item)

    return [
        NewsItem(
            heading=item.get("title"),
            summary=item.get("snippet"),
            source="serper",
            source_link=item.get("link"),
            image=item.get("imageUrl"),
            date=item.get("date", today),
        )
        for item in unique
    ]


# --- Quelle 3: Firecrawl ---

async def _get_firecrawl_news(domain: str) -> list[NewsItem]:
    # Newsroom-/Blog-URL per Serper suchen
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

    url = results[0]["link"]
    app = FirecrawlApp(api_key=get_settings().FIRECRAWL_API_KEY)
    result = await asyncio.to_thread(app.scrape_url(url, formats=["markdown"]))
    if not result.markdown:
        return []

    # LLM extrahiert News-Artikel aus dem gescrapten Text
    openai = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)
    response = await openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": (
                "Extract news articles from this text. "
                "Return a JSON array of objects with fields: heading, summary, source_link, date. "
                "Only include articles from today if possible. Max 5 articles."
            )},
            {"role": "user", "content": result.markdown[:4000]},
        ],
        response_format={"type": "json_object"},
    )

    articles = json.loads(response.choices[0].message.content).get("articles", [])
    return [
        NewsItem(
            heading=a.get("heading"),
            summary=a.get("summary"),
            source="firecrawl",
            source_link=a.get("source_link"),
            date=a.get("date", today),
        )
        for a in articles
    ]


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
