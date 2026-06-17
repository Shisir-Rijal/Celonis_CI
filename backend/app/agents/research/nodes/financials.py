import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from datetime import datetime, timezone
from app.agents.research.state import ResearchState, FinancialData
from app.agents.research.repositories.research_repository import insert_research_snapshot, snapshot_exists
from app.agents.shared.utils.finnhub import _get_symbol
from app.config import get_settings
import finnhub
import structlog
import httpx
import asyncio
from openai import AsyncOpenAI
import yfinance as yf



# API: https://finnhub.io/docs/api/

logger = structlog.get_logger(__name__)
settings = get_settings()

# Client
client = finnhub.Client(api_key=settings.FINNHUB_API_KEY)

# Revenue scraping if paid for API
# def _get_revenue_from_breakdown(client: finnhub.Client, ticker: str) -> float | None:
#     breakdown = client.stock_revenue_breakdown(ticker)
#     data = breakdown.get("data", [])
#     if not data:
#         return None
    
#     # neueste Periode nehmen
#     latest = data[0].get("breakdown", [])
#     total = sum(item.get("value", 0) for item in latest)
#     return total if total > 0 else None


# Analyst data scraping if paid for API
# def _get_analyst_trends(client: finnhub.Client, ticker: str) -> tuple[int, int, int]:
#     trends = client.recommendation_trends(ticker)
#     if not trends:
#         return None, None, None
#     latest = trends[0]  # neueste Periode
#     return latest.get("buy"), latest.get("hold"), latest.get("sell")

async def _get_analyst_trends(domain: str) -> tuple[int | None, int | None, int | None]:
    company = domain.replace(".com", "")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": get_settings().SERPER_API_KEY},
            json={"q": f"{company} stock analyst rating buy hold sell 2024", "num": 5},
            timeout=10,
        )
    snippets = " ".join(r.get("snippet", "") for r in response.json().get("organic", []))

    openai_client = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)
    result = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Extract analyst ratings from text. Return JSON: {\"buy\": int, \"hold\": int, \"sell\": int}. Use null if not found."},
            {"role": "user", "content": snippets},
        ],
        response_format={"type": "json_object"},
    )
    import json
    data = json.loads(result.choices[0].message.content)
    return data.get("buy"), data.get("hold"), data.get("sell")



def _get_price_history(ticker: str) -> dict[str, float]:
    hist = yf.Ticker(ticker).history(period="5y", interval="1mo")
    if hist.empty:
        return {}
    return {
        str(date)[:7]: round(float(price), 2)
        for date, price in hist["Close"].items()
    }


async def _scrape_financials(domain: str, company: str) -> FinancialData:
    client = finnhub.Client(api_key=settings.FINNHUB_API_KEY)

    ticker = _get_symbol(domain)
    if not ticker:
        return FinancialData(
            company=company,
            url=f"https://{domain}",
            title=f"Financials: {company}",
            on_stock_market=False,
        )

    print(f"Ticker found: {ticker}")
    quote, price_history, (buy, hold, sell) = await asyncio.gather(
        asyncio.to_thread(client.quote, ticker),
        asyncio.to_thread(_get_price_history, ticker),
        _get_analyst_trends(domain),
    )

    return FinancialData(
        # --- BaseData: dynamic fields (rest comes from class defaults) ---
        company=company,
        url=f"https://finance.yahoo.com/quote/{ticker}",
        title=f"Financials: {ticker}",
        # --- FinancialData-specific ---
        on_stock_market=True,
        current_stock_price=quote.get("c"),
        stock_change=quote.get("d"),
        percent_change=quote.get("dp"),
        analyst_buy=buy,
        analyst_hold=hold,
        analyst_sell=sell,
        price_history=price_history,
    )


async def run(state: ResearchState) -> dict:
    logger.info("Run Financials")
    domain = state["competitor_domain"]
    if snapshot_exists(domain, "financials"):
        logger.info("node_skipped_cached", node="financials", domain=domain)
        return {"completed_nodes": ["financials"]}
    company = domain.split(".")[0].capitalize()
    try:
        data = await _scrape_financials(domain, company)
        try:
            insert_research_snapshot(domain, datetime.now(timezone.utc), "financials", data)
        except Exception as db_err:
            logger.warning("snapshot_write_failed", node="financials", error=str(db_err))
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
        if result.get("errors"):
            print("Errors:", result["errors"])
        else:
            print(result["financials"].model_dump_json(indent=2))

    asyncio.run(main())
