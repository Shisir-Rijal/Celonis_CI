"""News Intelligence API router.

GET /news
    All competitors, latest news snapshot per company, with chip-filter support.

GET /news/{company}
    Single company's latest news snapshot.

All endpoints require a valid JWT via Authorization: Bearer <token>.
"""

import structlog
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel

from app.auth.dependencies import require_auth
from app.rag.supabase_client import get_supabase

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/news", tags=["news"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class NewsArticle(BaseModel):
    heading: str | None
    text: str | None
    summary: str | None
    url: str
    title: str | None
    image: str | None
    author: str | None
    published_date: str | None
    source_type: str | None


class CompanyNews(BaseModel):
    company: str          # domain, e.g. "celonis.com"
    name: str              # display name, e.g. "Celonis"
    run_at: datetime
    article_count: int
    frequency: dict[str, int]
    articles: list[NewsArticle]


class NewsListResponse(BaseModel):
    companies: list[CompanyNews]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_company_news(row: dict, name: str) -> CompanyNews:
    """Convert a research_snapshots row (node='news') to CompanyNews."""
    data = row["data"]
    items = data.get("news", [])

    articles = [
        NewsArticle(
            heading=item.get("heading"),
            text=item.get("text"),
            summary=item.get("summary"),
            url=item.get("url", ""),
            title=item.get("title"),
            image=item.get("image"),
            author=item.get("author"),
            published_date=item.get("published_date"),
            source_type=item.get("source_type"),
        )
        for item in items
    ]

    frequency: dict[str, int] = {}
    for item in items:
        date = item.get("published_date")
        if date:
            frequency[date] = frequency.get(date, 0) + 1

    return CompanyNews(
        company=row["company"],
        name=name,
        run_at=row["run_at"],
        article_count=len(articles),
        frequency=frequency,
        articles=articles,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=NewsListResponse)
async def list_news(
    companies: list[str] | None = Query(
        default=None,
        description="Filter by domain(s), e.g. ?companies=celonis.com&companies=sap.com. Omit for all active competitors.",
    ),
    _: None = Depends(require_auth),
) -> NewsListResponse:
    """Return the latest news snapshot for each active competitor.

    Powers the News Dashboard chip-filter — pass `companies` to narrow
    results, or omit to get all active competitors.

    Raises:
        500: Unexpected database error.
    """
    db = get_supabase()

    try:
        comp_query = db.table("competitors").select("domain, name").eq("active", True)
        if companies:
            comp_query = comp_query.in_("domain", companies)
        comp_resp = comp_query.execute()
    except Exception as exc:
        logger.error("competitors_query_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query competitors.",
        )

    competitors: list[dict] = comp_resp.data or []
    name_by_domain = {c["domain"]: c["name"] for c in competitors}
    domains = list(name_by_domain.keys())

    if not domains:
        return NewsListResponse(companies=[])

    try:
        snap_resp = (
            db.table("research_snapshots")
            .select("company, run_at, data")
            .eq("node", "news")
            .in_("company", domains)
            .order("run_at", desc=True)
            .execute()
        )
    except Exception as exc:
        logger.error("news_snapshots_query_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query news snapshots.",
        )

    rows: list[dict] = snap_resp.data or []

    # Keep only the latest row per company (rows are ordered run_at desc)
    latest_by_company: dict[str, dict] = {}
    for row in rows:
        company = row["company"]
        if company not in latest_by_company:
            latest_by_company[company] = row

    results = [
        _row_to_company_news(row, name_by_domain.get(company, company))
        for company, row in latest_by_company.items()
    ]

    return NewsListResponse(companies=results)


@router.get("/{company}", response_model=CompanyNews)
async def get_company_news(
    company: str,
    _: None = Depends(require_auth),
) -> CompanyNews:
    """Return the latest news snapshot for a single company.

    Args:
        company: Competitor domain, e.g. "celonis.com".

    Raises:
        404: No news snapshot found for this company.
        500: Unexpected database error.
    """
    db = get_supabase()

    try:
        comp_resp = (
            db.table("competitors")
            .select("domain, name")
            .eq("domain", company)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.error("competitors_query_failed", company=company, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query competitors.",
        )

    if not comp_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown company domain '{company}'.",
        )

    name = comp_resp.data[0]["name"]

    try:
        snap_resp = (
            db.table("research_snapshots")
            .select("company, run_at, data")
            .eq("company", company)
            .eq("node", "news")
            .order("run_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.error("news_snapshot_query_failed", company=company, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query news snapshot.",
        )

    if not snap_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No news snapshot found for company '{company}'.",
        )

    return _row_to_company_news(snap_resp.data[0], name)