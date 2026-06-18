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
RUNS_TABLE = "brand_geo_runs"


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


def insert_geo_run(
    company: str,
    run_at: datetime,
    synthesis: "GeoSynthesisOutput",
    recommendation_rate: float,
    client: Client | None = None,
) -> None:
    """Persist one synthesis result row to brand_geo_runs.

    One row per pipeline run. Enables delta tracking over time —
    compare any two run_at values to see how the strategic analysis changed.

    Args:
        company:   Company domain, e.g. "celonis.com".
        run_at:    Timestamp of the pipeline run.
        synthesis: Structured synthesis output from the GEO Intelligence node.
        client:    Optional Supabase client override for testing.
    """
    from app.prompts.brand.geo_synthesis import GeoSynthesisOutput  # local import avoids circular

    db = client or get_supabase()

    payload: dict[str, Any] = {
        "id": str(uuid4()),
        "company": company,
        "run_at": run_at.isoformat(),
        "mention_rate": synthesis.mention_rate,
        "recommendation_rate": recommendation_rate,
        "gap_keyword_count": synthesis.gap_keyword_count,
        "dominant_framing": synthesis.dominant_framing,
        "strongest_tier": synthesis.strongest_tier,
        "top_counter_positioning": synthesis.top_counter_positioning,
        "narrative": synthesis.narrative,
        "critical_gap": synthesis.critical_gap,
        "framing_gap": synthesis.framing_gap,
        "peer_group_assessment": synthesis.peer_group_assessment,
        "owned_territories": json.dumps(synthesis.owned_territories or []),
        "contested_territories": json.dumps(synthesis.contested_territories or []),
        "absent_territories": json.dumps(synthesis.absent_territories or []),
        "primary_peer_group": json.dumps(synthesis.primary_peer_group or []),
    }

    db.table(RUNS_TABLE).insert(
        {k: v for k, v in payload.items() if v is not None}
    ).execute()
