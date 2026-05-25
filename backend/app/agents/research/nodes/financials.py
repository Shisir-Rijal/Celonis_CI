import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from app.agents.research.state import ResearchState, FinancialData
import structlog
from supabase import create_client
from app.config import get_settings
import finnhub
from app.agents.shared.utils.finnhub import _get_symbol

# API: https://finnhub.io/docs/api/

logger = structlog.getLogger(__name__)
settings = get_settings()

# Client
client = finnhub.Client(api_key=settings.FINNHUB_API_KEY)


def _get_revenue_from_breakdown(client: finnhub.Client, ticker: str) -> float | None:
    breakdown = client.stock_revenue_breakdown(ticker)
    data = breakdown.get("data", [])
    if not data:
        return None
    
    # neueste Periode nehmen
    latest = data[0].get("breakdown", [])
    total = sum(item.get("value", 0) for item in latest)
    return total if total > 0 else None


def _get_analyst_trends(client: finnhub.Client, ticker: str) -> tuple[int, int, int]:
    trends = client.recommendation_trends(ticker)
    if not trends:
        return None, None, None
    latest = trends[0]  # neueste Periode
    return latest.get("buy"), latest.get("hold"), latest.get("sell")


def _scrape_financials(domain: str) -> FinancialData:
    client = finnhub.client(api_key=settings.FINNHUB_API_KEY)

    ticker = _get_symbol(client, domain)
    if not ticker:
        return FinancialData(on_stock_market=False, source="finnhub")
    
    quote = client.quote(ticker)
    profile = client.company_profile2(symbol=ticker)
    revenue = _get_revenue_from_breakdown(client, ticker)
    buy, hold, sell = _get_analyst_trends(client, ticker)
    
    return FinancialData(
        on_stock_market=True,
        current_stock_price = quote.get("c"),
        stock_change = quote.get("d"),
        percent_change = quote.get("dp"),
        market_cap = profile.get("marketCapitalization"),
        revenue=revenue,
        analyst_buy = buy,
        analyst_hold = hold,
        analyst_sell = sell,
        price_history = [],
        source="finnhub",
    )


async def run(state: ResearchState) -> dict:
    logger.info("Run Financials")
    domain = state["competitor_domain"]
    try: 
        data = _scrape_financials(domain)
        return {
            "financials": data,
            "completed_nodes": ["financials"],
        }
    except Exception as e:
        logger.error("node_failed", node="financials", error=str(e))
        return {"errors": [f"financials: {e}"]}
    



if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

    import asyncio
    import structlog
    structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

    from app.agents.research.state import ResearchState, VisualsData, PositioningData, FinancialData, SocialData, SeoGeoData, NewsData, EventsData, NewsletterData

    async def main():
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
        print(result["financials"].model_dump_json(indent=2))

    asyncio.run(main())
