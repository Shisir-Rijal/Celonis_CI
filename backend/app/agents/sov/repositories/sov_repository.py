"""backend/app/agents/sov/repositories/sov_repository.py

Typed repository helpers for the sov_mentions table.

The persist node passes classified Mentions to this module wrapped as
SovMentionRow dataclasses. All Supabase I/O for the SoV pipeline lives here.

Conflict handling: the table has a UNIQUE constraint on
(company, source_type, url). We use upsert with ignore_duplicates so that
re-runs against the same article do not raise — the existing row stays
untouched and no LLM re-classification is wasted.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import structlog
from supabase import Client

from app.rag.supabase_client import get_supabase

logger = structlog.get_logger(__name__)

TABLE = "sov_mentions"


@dataclass
class SovMentionRow:
    """One classified mention ready for insertion into sov_mentions.

    Field names map 1:1 to the table columns. Pure data carrier — no logic.
    Kept separate from the Pydantic Mention model so that persistence concerns
    do not leak into the domain model used inside the pipeline.
    """

    company: str
    run_at: datetime
    source_type: str
    source: str
    title: str
    content: str | None
    date: date
    month_bucket: str
    url: str
    language: str | None
    themes: list[str]
    region: str | None
    is_relevant: bool
    reasoning: str | None


def _to_payload(row: SovMentionRow) -> dict[str, Any]:
    """Serialise one SovMentionRow into a Supabase-ready dict.

    Date / datetime are converted to ISO strings; lists are passed through
    (supabase-py handles JSONB serialisation). None values are stripped so
    Postgres column defaults apply where set.
    """
    payload: dict[str, Any] = {
        "company": row.company,
        "run_at": row.run_at.isoformat(),
        "source_type": row.source_type,
        "source": row.source,
        "title": row.title,
        "content": row.content,
        "date": row.date.isoformat(),
        "month_bucket": row.month_bucket,
        "url": row.url,
        "language": row.language,
        "themes": row.themes,
        "region": row.region,
        "is_relevant": row.is_relevant,
        "reasoning": row.reasoning,
    }
    return {k: v for k, v in payload.items() if v is not None}


def insert_sov_mentions(
    rows: list[SovMentionRow],
    client: Client | None = None,
) -> int:
    """Bulk-upsert classified mentions, skipping any natural-key conflicts.

    Args:
        rows:   Classified mention rows to persist.
        client: Optional Supabase client override for testing.

    Returns:
        Number of rows submitted to the upsert. This is NOT the number of new
        rows actually inserted — with ignore_duplicates, Supabase does not
        report that distinction. Used only for logging / loose progress signal.

    Raises:
        Exception: any Supabase / network error is re-raised after logging.
    """
    if not rows:
        return 0

    db = client or get_supabase()
    payloads = [_to_payload(row) for row in rows]

    try:
        (
            db.table(TABLE)
            .upsert(
                payloads,
                on_conflict="company,source_type,url",
                ignore_duplicates=True,
            )
            .execute()
        )
    except Exception as exc:
        logger.error(
            "sov_repository_insert_failed",
            attempted=len(payloads),
            error=str(exc),
        )
        raise

    logger.info("sov_repository_insert_done", submitted=len(payloads))
    return len(payloads)
