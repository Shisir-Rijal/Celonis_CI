"""backend/app/agents/brand/repositories/geo_repository.py

Typed repository helpers for the brand_geo_sightings table.

Each row represents one keyword analysed in one pipeline run.
All database I/O goes through these helpers.

Issue #90: GEO Intelligence backend
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from supabase import Client

from app.rag.supabase_client import get_supabase

TABLE = "brand_geo_sightings"


@dataclass
class GeoSightingRow:
    """One keyword result row ready for insertion.

    Fields map 1:1 to brand_geo_sightings columns.
    Insight fields are None when the company was not mentioned
    or when the analysis LLM call failed.
    """

    company: str
    run_at: datetime
    keyword: str
    tier: str
    llm: str
    mentioned: bool
    context: str | None = None
    raw_response: str | None = None
    co_mentioned_companies: list[str] | None = None
    framing: str | None = None
    recommendation_strength: str | None = None
    use_case_context: str | None = None
    counter_positioning: str | None = None


def insert_geo_sighting(
    row: GeoSightingRow,
    client: Client | None = None,
) -> None:
    """Insert one GeoSightingRow into brand_geo_sightings.

    Args:
        row:    The sighting data to persist.
        client: Optional Supabase client override for testing.

    Raises:
        Exception: Propagates any Supabase error unchanged.
    """
    db = client or get_supabase()

    payload: dict[str, Any] = {
        "id": str(uuid4()),
        "company": row.company,
        "run_at": row.run_at.isoformat(),
        "keyword": row.keyword,
        "tier": row.tier,
        "llm": row.llm,
        "mentioned": row.mentioned,
        "context": row.context,
        "raw_response": row.raw_response,
        "co_mentioned_companies": (
            json.dumps(row.co_mentioned_companies)
            if row.co_mentioned_companies is not None
            else None
        ),
        "framing": row.framing,
        "recommendation_strength": row.recommendation_strength,
        "use_case_context": row.use_case_context,
        "counter_positioning": row.counter_positioning,
    }

    # Remove None values so Postgres uses column defaults where applicable
    payload = {k: v for k, v in payload.items() if v is not None}

    db.table(TABLE).insert(payload).execute()


def insert_geo_sightings(
    rows: list[GeoSightingRow],
    client: Client | None = None,
) -> None:
    """Bulk insert a list of GeoSightingRows.

    Inserts all rows in a single Supabase call.
    On failure the entire batch fails — caller should handle per-row
    fallback if partial persistence is needed.

    Args:
        rows:   List of sighting rows to persist.
        client: Optional Supabase client override for testing.
    """
    if not rows:
        return

    db = client or get_supabase()

    payloads = []
    for row in rows:
        payload: dict[str, Any] = {
            "id": str(uuid4()),
            "company": row.company,
            "run_at": row.run_at.isoformat(),
            "keyword": row.keyword,
            "tier": row.tier,
            "llm": row.llm,
            "mentioned": row.mentioned,
            "context": row.context,
            "raw_response": row.raw_response,
            "co_mentioned_companies": (
                json.dumps(row.co_mentioned_companies)
                if row.co_mentioned_companies is not None
                else None
            ),
            "framing": row.framing,
            "recommendation_strength": row.recommendation_strength,
            "use_case_context": row.use_case_context,
            "counter_positioning": row.counter_positioning,
        }
        payloads.append({k: v for k, v in payload.items() if v is not None})

    db.table(TABLE).insert(payloads).execute()
