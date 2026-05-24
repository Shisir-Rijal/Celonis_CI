from app.agents.research.state import ResearchState, SocialLinks
import logging

logger = logging.getLogger(__name__)

async def run(state: ResearchState) -> dict:
    logger.info("Run SocialLinks")
    return {
        "completed_nodes": state["completed_nodes"] + ["node_sociallinks"]
    }