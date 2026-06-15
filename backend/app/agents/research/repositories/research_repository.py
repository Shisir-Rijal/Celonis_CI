"""backend/app/agents/research/repositories/research_repository.py

Typed repository helpers for the research_snapshots table.

Each row represents one node's structured output for one pipeline run.
All database I/O goes through these helpers.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel
from supabase import Client

from app.rag.supabase_client import get_supabase

TABLE = "research_snapshots"


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
