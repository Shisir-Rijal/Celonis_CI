# Web scraping 
from app.agents.research.state import ResearchState, NewsData
import structlog
import httpx
import finnhub
from pydantic import BaseModel
from app.config import get_settings
from datetime import date
from app.agents.shared.utils.finnhub import _get_symbol


settings = get_settings()
logger = structlog.getLogger(__name__)
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


# --- Quelle 3: Firecrawl ---

async def _get_firecrawl_news(domain: str) -> list[NewsItem]:
    return [
        NewsItem(
            heading=item.get("headline"),
            summary=item.get("summary"),
            source=item.get("source"),
            source_link=item.get("url"),
            image=item.get("image"),
            date=today,
        )
        for item in articles
    ]



async def run(state: ResearchState) -> list[NewsItem]:
    domain = state["competitor_domain"]
    try:
        all_news: list[NewsItem] = []

        # Finnhub
        client = finnhub.Client(api_key=get_settings().FINNHUB_API_KEY)
        ticker = _get_symbol(client, domain)
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