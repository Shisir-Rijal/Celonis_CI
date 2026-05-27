import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import structlog
from app.agents.research.state import ResearchState, SocialData
from app.agents.shared.utils.brandfetch import _get_brand_data

logger = structlog.get_logger(__name__)

_PLATFORM_MAP = {
    "twitter": "twitter",
    "x": "twitter",
    "instagram": "instagram",
    "facebook": "facebook",
    "linkedin": "linkedin",
    "youtube": "youtube",
    "tiktok": "tiktok",
}


# Scrape Sociallinks:

async def _scrape_social_links(domain: str) -> dict[str, str]:
    data = await _get_brand_data(domain)
    links: dict[str, str] = {}
    for entry in data.get("links", []):
        name = (entry.get("name") or "").lower()
        url = entry.get("url")
        if url and name in _PLATFORM_MAP:
            links[_PLATFORM_MAP[name]] = url
    return links

async def _scrape_reddit_content_about(comypany: str):
    pass


async def _scrape_yt_content_about_(company: str):
    pass




async def run(state: ResearchState) -> dict:
    domain = state["competitor_domain"]
    company = domain.replace(".com", "").replace(".io", "")
    logger.info("Run Socials")

    try:
        social_links = await _scrape_social_links(domain)
        reddit_content = await _scrape_reddit_content_about(company)
        youtube_content = await _scrape_yt_content_about_(company)
        return {
            "socials": SocialData(
                social_links=social_links or None,
                reddit_content=reddit_content or None,
                youtube_content=youtube_content,
                source="brandfetch",
            ),
            "completed_nodes": ["socials"],
        }
    except Exception as e:
        logger.error("node_failed", node="socials", error=str(e))
        return {"errors": [f"socials: {e}"]}


if __name__ == "__main__":
    import asyncio
    structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

    async def main():
        from app.agents.research.state import VisualsData, PositioningData, FinancialData, SeoGeoData, NewsData, EventsData, NewsletterData

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
            print(result["socials"].model_dump_json(indent=2))

    asyncio.run(main())
