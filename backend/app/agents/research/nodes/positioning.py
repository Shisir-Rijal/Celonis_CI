import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import asyncio
import structlog
import httpx
import json
from openai import AsyncOpenAI
from firecrawl import FirecrawlApp
from app.agents.research.state import ResearchState, PositioningData
from app.config import get_settings


logger = structlog.get_logger(__name__)


async def _scrape_positioning(domain: str) -> PositioningData:
    # About-/Mission-Seite per Serper finden
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": get_settings().SERPER_API_KEY},
            json={"q": f"site:{domain} about OR mission OR vision OR values or careers or blogs or company", "num": 1},
            timeout=10,
        )
    results = response.json().get("organic", [])
    if not results:
        return PositioningData(source="firecrawl")

    url = results[0]["link"]
    app = FirecrawlApp(api_key=get_settings().FIRECRAWL_API_KEY)
    result = await asyncio.to_thread(app.scrape_url, url, formats=["markdown"])
    if not result.markdown:
        return PositioningData(source="firecrawl")

    openai = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)
    response = await openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": (
                "Extract company positioning from this text. "
                "Return a JSON object with fields: purpose, vision, mission, values (as object), employer_positioning (as object), blogs (as object), job_positing_employer_description. "
                "Use null if a field is not found."
            )},
            {"role": "user", "content": result.markdown[:4000]},
        ],
        response_format={"type": "json_object"},
    )

    data = json.loads(response.choices[0].message.content)
    return PositioningData(
        purpose=data.get("purpose"),
        vision=data.get("vision"),
        mission=data.get("mission"),
        values=data.get("values"),
        employer_positioning=data.get("employer_positioning"),
        job_positing_employer_description = data.get("job_positing_employer_description"),
        blogs=data.get("blogs"),
        source="firecrawl",
    )


async def run(state: ResearchState) -> dict[str, any]:
    domain = state["competitor_domain"]
    try:
        data = await _scrape_positioning(domain)
        return {
            "positioning": data,
            "completed_nodes": ["positioning"],
        }
    except Exception as e:
        logger.error("node_failed", node="positioning", error=str(e))
        return {"errors": [f"positioning: {e}"]}


if __name__ == "__main__":
    import asyncio
    structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

    async def main():
        from app.agents.research.state import VisualsData, FinancialData, SocialData, SeoGeoData, NewsData, EventsData, NewsletterData

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
            print(result["positioning"].model_dump_json(indent=2))

    asyncio.run(main())