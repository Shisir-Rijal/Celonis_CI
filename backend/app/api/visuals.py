"""Competitors / Visuals API router.

GET /competitors/colors
    Returns the best brand color per tracked company, derived from the
    latest visuals snapshot. Prefers the first chromatic (non grey/white/
    black) primary color; falls back to a chromatic secondary, then any
    non-white/black primary or secondary, if nothing chromatic is found.

GET /visuals
    Returns the full visuals payload (logo, colors, fonts, images, videos)
    from the latest snapshot per tracked company.

GET /visuals/{domain}
    Returns the full visuals payload for a single company by domain.

Requires a valid JWT via Authorization: Bearer <token>.
"""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.auth.dependencies import require_auth
from app.rag.supabase_client import get_supabase

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/competitors", tags=["competitors"])
visuals_router = APIRouter(prefix="/visuals", tags=["visuals"])

# ---------------------------------------------------------------------------
# Color picking
# ---------------------------------------------------------------------------

_EXCLUDED = {"#ffffff", "#fff", "#000000", "#000"}


def _valid(color: str) -> bool:
    return color.lower().strip() not in _EXCLUDED


def _is_grayscale(color: str) -> bool:
    """True for black/white/grey — R, G, B channels all close to equal.
    Catches near-black/near-white design-system foundation tones (e.g. IBM's
    #161616, #F4F4F4) that the exact-match _EXCLUDED list above misses,
    since those aren't the company's actual accent color either."""
    h = color.lstrip("#").strip()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return False
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return False
    return max(r, g, b) - min(r, g, b) <= 12


def _pick_color(colors_data: dict) -> str | None:
    """Prefer the first chromatic (non grey/white/black) primary color —
    that's the company's actual accent, not a neutral foundation tone.
    Falls back to the first chromatic secondary, then any valid primary,
    then any valid secondary, if nothing chromatic is found anywhere."""
    primary = [c for c in (colors_data.get("primary") or []) if _valid(c)]
    secondary = [c for c in (colors_data.get("secondary") or []) if _valid(c)]

    chromatic_primary = [c for c in primary if not _is_grayscale(c)]
    if chromatic_primary:
        return chromatic_primary[0]

    chromatic_secondary = [c for c in secondary if not _is_grayscale(c)]
    if chromatic_secondary:
        return chromatic_secondary[0]

    if primary:
        return primary[0]
    if secondary:
        return secondary[0]

    return None


# ---------------------------------------------------------------------------
# Full visuals response models
# ---------------------------------------------------------------------------

class FontInfoOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    type: str | None = None
    weights: list[str] | None = None
    sizes: list[str] | None = None


class SourcedAssetOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str
    source_page: str | None = None
    category: str | None = None


class VisualsItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    company: str
    url: str | None = None
    title: str | None = None
    logo: list[str] = []
    colors: dict[str, Any] = {}  # {"primary": [...], "secondary": [...], "semantic": {hex: label}}
    fonts: list[FontInfoOut] | None = None
    images: list[SourcedAssetOut] | None = None
    videos: list[SourcedAssetOut] = []
    icons: dict[str, str] | None = None
    run_at: str | None = None


class VisualsResponse(BaseModel):
    visuals: list[VisualsItem]
    total: int
    latest_run_at: str | None = None


def _latest_visuals_rows(domain: str | None = None) -> list[dict]:
    """Query research_snapshots for node='visuals', optionally filtered by domain."""
    db = get_supabase()
    query = (
        db.table("research_snapshots")
        .select("company, run_at, data")
        .eq("node", "visuals")
        .order("run_at", desc=True)
    )
    if domain:
        query = query.eq("company", domain)
    resp = query.execute()
    rows: list[dict] = resp.data or []

    # Keep only the latest snapshot per company (rows already desc by run_at)
    seen: set[str] = set()
    latest_rows: list[dict] = []
    for row in rows:
        company = row.get("company") or ""
        if company not in seen:
            seen.add(company)
            latest_rows.append(row)
    return latest_rows


def _row_to_item(row: dict) -> VisualsItem:
    data: dict = row.get("data") or {}
    domain: str = row.get("company") or ""
    payload = {**data, "company": data.get("company") or domain, "run_at": row.get("run_at")}
    return VisualsItem(**payload)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@visuals_router.get("", response_model=VisualsResponse)
async def get_visuals(
    _: None = Depends(require_auth),
) -> VisualsResponse:
    """Return the full visuals payload (logo, colors, fonts, images, videos)
    from the latest snapshot per tracked company.

    Raises:
        500: Unexpected database error.
    """
    try:
        rows = _latest_visuals_rows()
    except Exception as exc:
        logger.error("visuals_query_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query visuals snapshots.",
        )

    items = [_row_to_item(row) for row in rows]
    latest_run_at: str | None = max((r.get("run_at") for r in rows), default=None)

    return VisualsResponse(
        visuals=items,
        total=len(items),
        latest_run_at=latest_run_at,
    )


@visuals_router.get("/{domain}", response_model=VisualsItem)
async def get_visuals_for_domain(
    domain: str,
    _: None = Depends(require_auth),
) -> VisualsItem:
    """Return the full visuals payload for a single company by domain.

    Raises:
        404: No visuals snapshot found for this domain.
        500: Unexpected database error.
    """
    try:
        rows = _latest_visuals_rows(domain)
    except Exception as exc:
        logger.error("visuals_query_failed", domain=domain, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query visuals snapshots.",
        )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No visuals snapshot found for domain '{domain}'.",
        )

    return _row_to_item(rows[0])


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/colors", response_model=dict[str, str])
async def get_competitor_colors(
    _: None = Depends(require_auth),
) -> dict[str, str]:
    """Return a company → hex color map derived from the latest visuals snapshot.

    Only companies with a visuals snapshot are included. Companies whose
    scraped colors are all white/black are omitted (frontend falls back to
    the palette).
    """
    db = get_supabase()

    try:
        resp = (
            db.table("research_snapshots")
            .select("company, run_at, data")
            .eq("node", "visuals")
            .order("run_at", desc=True)
            .execute()
        )
    except Exception as exc:
        logger.error("competitor_colors_query_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query visuals snapshots.",
        )

    rows: list[dict] = resp.data or []

    # Keep only the latest snapshot per company
    seen: set[str] = set()
    result: dict[str, str] = {}

    for row in rows:
        domain: str = row.get("company") or ""
        if not domain or domain in seen:
            continue
        seen.add(domain)

        data_blob: dict = row.get("data") or {}
        # Use the human-readable name stored inside the snapshot (e.g. "Celonis"),
        # which matches event.company in the frontend. Fall back to capitalising the
        # domain prefix so the key is always consistent with events.py.
        company_name: str = data_blob.get("company") or domain.split(".")[0].capitalize()

        colors_data: dict = data_blob.get("colors") or {}
        color = _pick_color(colors_data)
        if color:
            result[company_name] = color

    return result