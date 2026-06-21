"""backend/app/agents/visualbranding/repositories/visualbranding_repository.py

Typed repository helpers for the visualbranding_snapshots table.

Unlike research_snapshots (keyed per competitor), every row here is a
CROSS-COMPETITOR analysis — one visualbranding node's interpreted output for
one pipeline run, with no `company` column. Each row also carries a
`source_fingerprint`: a hash of the raw scraped data the analysis was built
from, so the graph's change-detection router (see graph.py) can tell whether
a node's source data actually changed since its last run, without having to
re-run the (expensive, LLM-backed) interpretation just to find out.
"""

import hashlib
import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from supabase import Client

from app.rag.supabase_client import get_supabase

TABLE = "visualbranding_snapshots"


def compute_fingerprint(payload: Any) -> str:
    """Stable hash of any JSON-serializable payload — used to detect whether
    a node's source data changed since the last time it ran."""
    normalized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode()).hexdigest()


def get_latest_fingerprint(node: str, client: Client | None = None) -> str | None:
    """Return the source_fingerprint recorded by the most recent run of `node`, or None
    if `node` has never run before (e.g. first-ever pipeline run)."""
    db = client or get_supabase()
    result = (
        db.table(TABLE)
        .select("source_fingerprint")
        .eq("node", node)
        .order("run_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0]["source_fingerprint"] if rows else None


def get_latest_analysis(node: str, client: Client | None = None) -> dict | None:
    """Return the data payload of the most recent analysis for `node`, or None."""
    db = client or get_supabase()
    result = (
        db.table(TABLE)
        .select("data")
        .eq("node", node)
        .order("run_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0]["data"] if rows else None


def insert_visualbranding_snapshot(
    node: str,
    run_at: datetime,
    source_fingerprint: str,
    data: BaseModel,
    client: Client | None = None,
) -> None:
    """Persist one visualbranding node's interpreted output.

    Args:
        node:               Node name, e.g. "colors", "fonts", "logos".
        run_at:             Timestamp of this pipeline run.
        source_fingerprint: Hash of the raw scraped data this analysis was built from —
                             compare against `get_latest_fingerprint` to skip re-running
                             a node whose source data hasn't changed.
        data:               Pydantic model output from the node (e.g. ColorAnalysis).
        client:             Optional Supabase client override for testing.

    Raises:
        Exception: Propagates any Supabase error unchanged.
    """
    db = client or get_supabase()

    payload: dict[str, Any] = {
        "node": node,
        "run_at": run_at.isoformat(),
        "source_fingerprint": source_fingerprint,
        "data": data.model_dump(mode="json"),
    }

    db.table(TABLE).insert(payload).execute()
