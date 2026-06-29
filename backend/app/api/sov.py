"""Share-of-Voice agent API router.

GET /sov
    Return all persisted SoV mentions plus light metadata. The dashboard
    aggregates / filters client-side, mirroring the /events pattern.

POST /sov/run
    Kick off one SoV pipeline run: load news + SEO from research_snapshots,
    classify via LLM, persist relevant mentions to sov_mentions.

A run takes 2-3 minutes for ~400 mentions; clients should set a long timeout.
The run endpoint is idempotent (URL pre-filter + ON CONFLICT) — re-running
against the same underlying research data is cheap and safe.

All endpoints require a valid JWT via Authorization: Bearer <token>.
"""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.agents.shared.competitors import get_competitor_domains
from app.agents.sov.graph import sov_graph
from app.auth.dependencies import require_auth
from app.rag.supabase_client import get_supabase

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/sov", tags=["sov"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class SovMention(BaseModel):
    """One classified mention row, mirroring the sov_mentions table."""

    id: str
    run_at: str
    company: str
    source_type: str            # 'news' | 'seo'
    source: str                 # 'finnhub' | 'serper' | 'firecrawl' | 'google_serp'
    title: str
    content: str | None
    date: str                   # ISO YYYY-MM-DD
    month_bucket: str           # YYYY-MM
    url: str
    language: str | None
    themes: list[str]
    region: str | None          # 'DACH' | 'Europe' | 'NA' | 'APAC' | 'Global'
    is_relevant: bool
    reasoning: str | None


class SovListResponse(BaseModel):
    """Dashboard payload: all persisted mentions plus index metadata.

    Frontend aggregates / filters client-side (matches the /events pattern).
    """

    mentions: list[SovMention]
    total: int
    latest_run_at: str | None
    companies: list[str]        # distinct, sorted, for stable color mapping


class SovRunResponse(BaseModel):
    """Summary of one SoV pipeline run.

    Counts walk down the pipeline funnel:
      companies → candidates_loaded → classified → persisted_count

    errors collects per-mention / per-source failures encountered along the
    way. A non-empty errors list with a non-zero persisted_count means
    "partial success" — usually fine.
    """

    run_at: datetime
    companies: int
    candidates_loaded: int
    classified: int
    persisted_count: int
    errors: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=SovListResponse)
async def list_sov_mentions(
    _: None = Depends(require_auth),
) -> SovListResponse:
    """Return all persisted SoV mentions sorted by publication date desc.

    No filtering, no aggregation — the dashboard handles that client-side.

    Raises:
        500: Unexpected database error.
    """
    db = get_supabase()

    try:
        resp = (
            db.table("sov_mentions")
            .select(
                "id, run_at, company, source_type, source, title, content, "
                "date, month_bucket, url, language, themes, region, "
                "is_relevant, reasoning"
            )
            .order("date", desc=True)
            .execute()
        )
    except Exception as exc:
        logger.error("sov_list_query_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query SoV mentions.",
        )

    rows: list[dict] = resp.data or []
    mentions = [SovMention(**row) for row in rows]

    latest_run_at = max((row["run_at"] for row in rows), default=None)
    companies = sorted({row["company"] for row in rows})

    logger.info("sov_list_done", mentions=len(mentions), companies=len(companies))

    return SovListResponse(
        mentions=mentions,
        total=len(mentions),
        latest_run_at=latest_run_at,
        companies=companies,
    )


@router.post("/run", response_model=SovRunResponse)
async def trigger_sov_run(
    _: None = Depends(require_auth),
) -> SovRunResponse:
    """Trigger one SoV agent run.

    Loads news + SEO snapshots for every active competitor, classifies each
    mention with an LLM, then persists the relevant ones.

    Raises:
        500: Failed to load competitor list, or pipeline crashed entirely.
             Per-mention failures are reported in the 200 response's `errors`.
    """
    run_at = datetime.now(timezone.utc)

    try:
        companies = await get_competitor_domains()
    except Exception as exc:
        logger.error("sov_run_get_competitors_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load competitor list from database.",
        )

    if not companies:
        logger.warning("sov_run_no_active_competitors")
        return SovRunResponse(
            run_at=run_at,
            companies=0,
            candidates_loaded=0,
            classified=0,
            persisted_count=0,
            errors=["no active competitors in competitors table"],
        )

    initial_state = {
        "run_at": run_at,
        "companies": companies,
        "candidate_mentions": [],
        "classified_mentions": [],
        "persisted_count": 0,
        "errors": [],
    }

    logger.info(
        "sov_run_started",
        companies=len(companies),
        run_at=run_at.isoformat(),
    )

    try:
        result = await sov_graph.ainvoke(initial_state)
    except Exception as exc:
        logger.error("sov_run_graph_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SoV pipeline crashed: {exc}",
        )

    response = SovRunResponse(
        run_at=run_at,
        companies=len(companies),
        candidates_loaded=len(result.get("candidate_mentions", [])),
        classified=len(result.get("classified_mentions", [])),
        persisted_count=result.get("persisted_count", 0),
        errors=result.get("errors", []),
    )

    logger.info(
        "sov_run_done",
        companies=response.companies,
        candidates=response.candidates_loaded,
        classified=response.classified,
        persisted=response.persisted_count,
        errors=len(response.errors),
    )

    return response
