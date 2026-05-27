from app.agents.research.state import ResearchState, SocialData
import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class SocialLinks(BaseModel):
    instagram: str | None = None
    linkedin: str | None = None
    facebook: str | None = None
    reddit: str | None = None
    youtube: str | None = None
    tiktok: str | None = None
    website: str | None = None

async def run(state: ResearchState) -> dict:
    logger.info("Run Socials")
    return {
        "completed_nodes": state["completed_nodes"] + ["node_socials"]
    }