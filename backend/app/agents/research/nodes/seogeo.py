import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import asyncio
import re
import httpx
import structlog
from openai import AsyncOpenAI

from app.agents.research.state import ResearchState, SeoGeoData, SeoKeywordSighting, GeoKeywordSighting
from app.config import get_settings

logger = structlog.get_logger(__name__)

KEYWORDS = [
    "Acquisition",
    "Agentic AI",
    "AIP",
    "Automation",
    "Autopilot",
    "Blueprint",
    "Consulting",
    "Continuous",
    "Discovery",
    "Copilot",
    "Creator",
    "Workflows",
    "Data Fabric",
    "Digital Twin",
    "Foundry",
    "GenAI",
    "Joule",
    "Object-Centric Process Mining",
    "OCPM",
    "Ontology",
    "Automate Process",
    "AI Process Intelligence",
    "Process Mining",
    "Signavio",
    "Supply Chain",
    "Transformation",
    "watsonx",
    "Workflow Intelligence",
]


# --- SEO: Google keyword visibility ---

async def _check_seo_keyword(
    keyword: str, domain: str, client: httpx.AsyncClient
) -> SeoKeywordSighting:
    try:
        resp = await client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": get_settings().SERPER_API_KEY},
            json={"q": keyword, "num": 50},
            timeout=10,
        )
        results = resp.json().get("organic", [])
        for i, result in enumerate(results, 1):
            if domain in result.get("link", ""):
                return SeoKeywordSighting(
                    keyword=keyword,
                    company_mentioned=True,
                    position=i,
                    link=result.get("link"),
                )
    except Exception as e:
        logger.warning("seo_keyword_failed", keyword=keyword, error=str(e))
    return SeoKeywordSighting(keyword=keyword, company_mentioned=False)


async def _seo_keyword_search(domain: str) -> list[SeoKeywordSighting]:
    async with httpx.AsyncClient() as client:
        tasks = [_check_seo_keyword(kw, domain, client) for kw in KEYWORDS]
        return list(await asyncio.gather(*tasks))


# --- GEO: LLM keyword visibility ---

_GEO_PROMPT = "Answer concisely. List the main companies or products known for this topic."


def _build_llm_clients() -> list[tuple[str, AsyncOpenAI, str]]:
    """Return (llm_name, client, model) for all configured LLMs."""
    settings = get_settings()
    clients: list[tuple[str, AsyncOpenAI, str]] = [
        ("gpt-4o-mini", AsyncOpenAI(api_key=settings.OPENAI_API_KEY), "gpt-4o-mini"),
    ]
    if settings.GEMINI_API_KEY:
        clients.append((
            "gemini-2.0-flash",
            AsyncOpenAI(
                api_key=settings.GEMINI_API_KEY,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            ),
            "gemini-2.0-flash",
        ))
    return clients


async def _check_geo_keyword(
    keyword: str, company: str, client: AsyncOpenAI, llm_name: str, model: str
) -> GeoKeywordSighting:
    for attempt in range(2):
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _GEO_PROMPT},
                    {"role": "user", "content": f"Which companies or platforms are the leading providers for: {keyword}?"},
                ],
            )
            answer = resp.choices[0].message.content or ""
            mentioned = company.lower() in answer.lower()
            context = None
            if mentioned:
                idx = answer.lower().find(company.lower())
                start = max(0, idx - 80)
                end = min(len(answer), idx + 150)
                context = answer[start:end].strip()
            return GeoKeywordSighting(
                keyword=keyword,
                llm=llm_name,
                company_mentioned=mentioned,
                context=context,
            )
        except Exception as e:
            err = str(e)
            if "429" in err:
                if "PerDay" in err:
                    raise RuntimeError(f"daily_quota_exhausted:{llm_name}")
                match = re.search(r'retryDelay[^\d]+(\d+)s', err)
                delay = int(match.group(1)) + 2 if match else 65
                logger.warning("geo_rate_limited", keyword=keyword, llm=llm_name, retry_in=delay, attempt=attempt + 1)
                await asyncio.sleep(delay)
            else:
                logger.warning("geo_keyword_failed", keyword=keyword, llm=llm_name, error=err)
                break
    return GeoKeywordSighting(keyword=keyword, llm=llm_name, company_mentioned=False)


_CONCURRENCY = {
    "gpt-4o-mini": 5,
    "gemini-2.0-flash": 1,  # free tier: 15 RPM → 1 at a time + 4s delay
}
_DELAY_AFTER = {
    "gemini-2.0-flash": 4.0,
}


async def _geo_keyword_search(company: str) -> list[GeoKeywordSighting]:
    llm_clients = _build_llm_clients()
    sems = {name: asyncio.Semaphore(_CONCURRENCY.get(name, 5)) for name, _, _ in llm_clients}
    disabled: set[str] = set()

    async def _throttled(kw: str, client: AsyncOpenAI, llm_name: str, model: str) -> GeoKeywordSighting:
        if llm_name in disabled:
            return GeoKeywordSighting(keyword=kw, llm=llm_name, company_mentioned=False)
        async with sems[llm_name]:
            try:
                result = await _check_geo_keyword(kw, company, client, llm_name, model)
            except RuntimeError as e:
                if "daily_quota_exhausted" in str(e):
                    logger.warning("geo_llm_disabled", llm=llm_name, reason="daily_quota_exhausted")
                    disabled.add(llm_name)
                return GeoKeywordSighting(keyword=kw, llm=llm_name, company_mentioned=False)
            if delay := _DELAY_AFTER.get(llm_name):
                await asyncio.sleep(delay)
            return result

    tasks = [
        _throttled(kw, client, llm_name, model)
        for kw in KEYWORDS
        for llm_name, client, model in llm_clients
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    n = len(llm_clients)
    return [
        r if isinstance(r, GeoKeywordSighting)
        else GeoKeywordSighting(keyword=KEYWORDS[i // n], llm="unknown", company_mentioned=False)
        for i, r in enumerate(results)
    ]


# --- Node entry point ---

async def run(state: ResearchState) -> dict:
    domain = state["competitor_domain"]
    company = domain.split(".")[0].capitalize()
    logger.info("run_seogeo", domain=domain)

    try:
        seo_sightings, geo_sightings = await asyncio.gather(
            _seo_keyword_search(domain),
            _geo_keyword_search(company),
        )

        return {
            "seogeo": SeoGeoData(
                seo=seo_sightings,
                geo=geo_sightings,
                source="serper+openai",
            ),
            "completed_nodes": ["seogeo"],
        }

    except Exception as e:
        logger.error("node_failed", node="seogeo", error=str(e))
        return {"errors": [f"seogeo: {e}"]}


if __name__ == "__main__":
    structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

    async def main():
        from app.agents.research.state import (
            VisualsData, PositioningData, FinancialData, SocialData,
            NewsData, EventsData, NewsletterData,
        )
        state = ResearchState(
            competitor_domain="celonis.com",
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
            print(result["seogeo"].model_dump_json(indent=2))

    asyncio.run(main())
