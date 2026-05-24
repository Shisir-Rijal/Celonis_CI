from app.agents.research.state import ResearchState, NewsletterData
import logging

logger = logging.getLogger(__name__)

async def run(state: ResearchState) -> dict:
    logger.info("Run Newsletter")
    return {
        "completed_nodes": state["completed_nodes"] + ["node_newsletter"]
    }