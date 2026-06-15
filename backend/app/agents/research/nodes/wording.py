import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import structlog
from app.agents.research.state import ResearchState

logger = structlog.get_logger(__name__)


async def run(_state: ResearchState) -> dict:
    # TODO: implement wording node (brand language, taglines, Finnhub company profile)
    logger.warning("node_skipped", node="wording", reason="not implemented yet")
    return {"errors": ["wording: not implemented yet"]}
