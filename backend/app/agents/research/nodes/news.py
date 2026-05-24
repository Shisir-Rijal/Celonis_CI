# Web scraping 
from app.agents.research.state import ResearchState, NewsData
import logging

logger = logging.getLogger(__name__)

async def run(state: ResearchState) -> dict:
    logger.info("Run News")
    stocks = {}
    return {
        "completed_nodes": state["completed_nodes"] + ["node_news"]
    }