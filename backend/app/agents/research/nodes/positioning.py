import structlog
import httpx
from openai import AsyncOpenAI
from pydantic import BaseModel
from firecrawl import FirecrawlApp
from app.agents.research.state import ResearchState, PositioningData, NewsletterData
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)


async def run(state: ResearchState) -> dict:
    logger.info("Run Positioning")
    return {
        "completed_nodes": state["completed_nodes"] + ["node_positioning"]
    }