"""Reports API router.

POST /reports/generate
    Generate a competitive intelligence report for a given topic.
    Returns a markdown string.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.dependencies import require_auth
from app.agents.report.agent import generate_report

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])

VALID_TOPICS = {"news", "events", "geo", "branding", "sov"}


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ReportRequest(BaseModel):
    topic: str
    companies: list[str] | None = None


class ReportResponse(BaseModel):
    topic: str
    companies: list[str] | None
    markdown: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/generate", response_model=ReportResponse)
async def generate_report_endpoint(
    request: ReportRequest,
    _: None = Depends(require_auth),
) -> ReportResponse:
    """Generate a competitive intelligence report for the given topic.

    Args:
        request.topic: One of 'news', 'events', 'geo', 'branding'.
        request.companies: Optional list of domains to filter by.
                           Omit to include all active competitors.
                           Ignored for branding.

    Raises:
        400: Invalid topic.
        500: Data fetch or LLM call failed.
    """
    if request.topic not in VALID_TOPICS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid topic '{request.topic}'. Valid topics: {sorted(VALID_TOPICS)}",
        )

    try:
        markdown = await generate_report(
            topic=request.topic,
            companies=request.companies,
        )
    except RuntimeError as exc:
        logger.error("report_generation_failed", topic=request.topic, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    return ReportResponse(
        topic=request.topic,
        companies=request.companies,
        markdown=markdown,
    )