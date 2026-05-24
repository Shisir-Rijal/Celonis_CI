from app.agents.research.state import ResearchState, VisualsData
import logging

logger = logging.getLogger(__name__)

async def run(state: ResearchState) -> dict:
    logger.info("Run Visuals")
    return {
        "completed_nodes": state["completed_nodes"] + ["node_visuals"]
    }