import logging
from app.agents.research.state import ResearchState, SeoGeoData

logger = logging.getLogger(__name__)


async def run(state: ResearchState) -> dict:
    logger.info("Run SeoGeo")
    return {
        "completed_nodes": state["completed_nodes"] + ["node_seogeo"]
    }

# SEO API finden
# GEO verschiedene modelle suchanfragen testen