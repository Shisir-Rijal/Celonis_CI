"""Competitors API router.

GET /competitors/colors
    Returns the best brand color per tracked company, derived from the
    latest visuals snapshot. Excludes pure white (#ffffff) and pure black
    (#000000). Falls back to first secondary color when primary only
    contains those two.

Requires a valid JWT via Authorization: Bearer <token>.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import require_auth
from app.rag.supabase_client import get_supabase

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/competitors", tags=["competitors"])

# ---------------------------------------------------------------------------
# Color picking
# ---------------------------------------------------------------------------

_EXCLUDED = {"#ffffff", "#fff", "#000000", "#000"}


def _valid(color: str) -> bool:
    return color.lower().strip() not in _EXCLUDED


def _pick_color(colors_data: dict) -> str | None:
    """Return the first valid primary color, or first valid secondary color."""
    primary = [c for c in (colors_data.get("primary") or []) if _valid(c)]
    if primary:
        return primary[0]

    secondary = [c for c in (colors_data.get("secondary") or []) if _valid(c)]
    if secondary:
        return secondary[0]

    return None


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