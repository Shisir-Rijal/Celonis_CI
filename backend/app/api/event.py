"""Events API router.

GET /events
    Return all scraped events from the latest research snapshot per company,
    flattened from website_events / luma_events / meetup_events / reported_events.

Requires a valid JWT via Authorization: Bearer <token>.
"""

from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
import re

from pydantic import BaseModel, ConfigDict, field_validator

from app.auth.dependencies import require_auth
from app.rag.supabase_client import get_supabase

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/events", tags=["events"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class EventItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    company: str
    name: str | None = None
    title: str | None = None
    event_date: str | None = None
    end_date: str | None = None
    location: str | None = None
    event_topic: str | None = None
    organized_by: str | None = None
    sponsors: list[str] | None = None
    speakers: list[str] | None = None
    summary: str | list[str] | None = None
    source_link: str | None = None
    image: str | None = None
    attendees: int | None = None
    source_type: str | None = None

    @field_validator("attendees", mode="before")
    @classmethod
    def coerce_attendees(cls, v: object) -> int | None:
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        if isinstance(v, str):
            m = re.match(r"[\d,]+", v.strip())
            if m:
                return int(m.group().replace(",", ""))
        return None
    date: str | None = None
    url: str | None = None


class EventsResponse(BaseModel):
    events: list[EventItem]
    total: int
    latest_run_at: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flatten_events(snapshot: dict) -> list[dict]:
    """Flatten all four event lists from a single research_snapshots row."""
    data: dict = snapshot.get("data") or {}
    company: str = snapshot.get("company") or ""

    events: list[dict] = []
    for key in ("website_events", "luma_events", "meetup_events", "reported_events"):
        for raw in data.get(key) or []:
            if not isinstance(raw, dict):
                continue
            if not raw.get("company"):
                raw = {**raw, "company": company}
            events.append(raw)
    return events


def _sort_key(event: dict) -> tuple:
    """Sort by event_date desc; events with no date sink to the bottom."""
    raw = event.get("event_date") or ""
    try:
        return (0, datetime.fromisoformat(raw.replace("Z", "+00:00")))
    except (ValueError, AttributeError):
        return (1, datetime.min)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("", response_model=EventsResponse)
async def get_events(
    _: None = Depends(require_auth),
) -> EventsResponse:
    """Return all scraped events across all tracked competitors.

    Reads research_snapshots where node='events', takes the latest snapshot
    per company, flattens the four event-source lists, and sorts by
    event_date descending.

    Raises:
        500: Unexpected database error.
    """
    db = get_supabase()

    try:
        resp = (
            db.table("research_snapshots")
            .select("company, run_at, data")
            .eq("node", "events")
            .order("run_at", desc=True)
            .execute()
        )
    except Exception as exc:
        logger.error("events_query_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query event snapshots.",
        )

    rows: list[dict] = resp.data or []

    # Keep only the latest snapshot per company (rows already desc by run_at)
    seen: set[str] = set()
    latest_snapshots: list[dict] = []
    for row in rows:
        company = row.get("company") or ""
        if company not in seen:
            seen.add(company)
            latest_snapshots.append(row)

    # Flatten and sort
    all_events: list[dict] = []
    for snapshot in latest_snapshots:
        all_events.extend(_flatten_events(snapshot))

    all_events.sort(key=_sort_key, reverse=True)

    event_items = [EventItem(**e) for e in all_events]

    # latest_run_at = most recent snapshot timestamp across all companies
    latest_run_at: str | None = rows[0].get("run_at") if rows else None

    return EventsResponse(
        events=event_items,
        total=len(event_items),
        latest_run_at=latest_run_at,
    )
