"""backend/app/agents/research/repositories/research_repository.py

Typed repository helpers for the research_snapshots table.

Each row represents one node's structured output for one pipeline run.
All database I/O goes through these helpers.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel
from supabase import Client

from app.rag.supabase_client import get_supabase

TABLE = "research_snapshots"


def snapshot_exists(
    company: str,
    node: str,
    max_age_hours: int = 24,
    client: Client | None = None,
) -> bool:
    """Return True if a fresh snapshot for (company, node) already exists.

    A snapshot is considered fresh when its run_at timestamp is within the
    last max_age_hours. Pass max_age_hours=0 to match any existing row
    regardless of age.
    """
    if os.getenv("RESEARCH_FORCE") == "1":
        return False
    db = client or get_supabase()
    result = (
        db.table(TABLE)
        .select("run_at")
        .eq("company", company)
        .eq("node", node)
        .order("run_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    if not rows:
        return False
    if max_age_hours <= 0:
        return True
    last_run = datetime.fromisoformat(rows[0]["run_at"])
    if last_run.tzinfo is None:
        last_run = last_run.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - last_run < timedelta(hours=max_age_hours)


def get_latest_snapshot(
    company: str,
    node: str,
    client: Client | None = None,
) -> dict | None:
    """Return the data payload of the most recent snapshot for (company, node), or None."""
    db = client or get_supabase()
    result = (
        db.table(TABLE)
        .select("data")
        .eq("company", company)
        .eq("node", node)
        .order("run_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0]["data"] if rows else None


def insert_research_snapshot(
    company: str,
    run_at: datetime,
    node: str,
    data: BaseModel,
    client: Client | None = None,
) -> None:
    """Persist one research node output to research_snapshots.

    Args:
        company: Competitor domain, e.g. "celonis.com".
        run_at:  Timestamp of the pipeline run.
        node:    Node name, e.g. "financials", "news", "seogeo".
        data:    Pydantic model output from the node.
        client:  Optional Supabase client override for testing.

    Raises:
        Exception: Propagates any Supabase error unchanged.
    """
    db = client or get_supabase()

    payload: dict[str, Any] = {
        "company": company,
        "run_at": run_at.isoformat(),
        "node": node,
        "data": data.model_dump(mode="json"),
    }

    db.table(TABLE).insert(payload).execute()
