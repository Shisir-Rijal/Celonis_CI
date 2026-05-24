from app.agents.research.state import ResearchState, FinancialData
import logging

logger = logging.getLogger(__name__)

async def run(state: ResearchState) -> dict:
    logger.info("Run Financials")
    stocks = {}
    return {
        "completed_nodes": state["completed_nodes"] + ["node_financials"]
    }