from app.agents.research.state import ResearchState, EventsData
import logging


logger = logging.getLogger(__name__)


async def run(state: ResearchState) -> dict:
    logger.info("Run Events")
    return {
        "completed_nodes": state["completed_nodes"] + ["node_events"]
    }
