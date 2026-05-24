from app.agents.research.state import ResearchState, SocialData
import logging

logger = logging.getLogger(__name__)

async def run(state: ResearchState) -> dict:
    logger.info("Run Socials")
    return {
        "completed_nodes": state["completed_nodes"] + ["node_socials"]
    }