"""backend/app/agents/sov/nodes/persist.py

Phase 3 of the SoV pipeline: write classified mentions to sov_mentions.

Mentions where is_relevant=False are dropped here — they were classified so
we have an audit trail in logs, but they should not influence SoV percentages
and we do not pay storage for them.

The natural-key UNIQUE on (company, source_type, url) plus ignore_duplicates
in the upsert prevent double-counting when runs overlap. A complete persist
failure (network error) is captured in state['errors'] without crashing the
graph — so callers can still see how many mentions reached this stage.
"""

from datetime import datetime

import structlog

from app.agents.sov.repositories.sov_repository import (
    SovMentionRow,
    insert_sov_mentions,
)
from app.agents.sov.state import Mention, SovPipelineState

logger = structlog.get_logger(__name__)


def _to_row(mention: Mention, run_at: datetime) -> SovMentionRow:
    """Convert a classified Mention to a SovMentionRow for insertion."""
    return SovMentionRow(
        company=mention.company,
        run_at=run_at,
        source_type=mention.source_type,
        source=mention.source,
        title=mention.title,
        content=mention.content,
        date=mention.date,
        month_bucket=mention.month_bucket,
        url=mention.url,
        language=mention.language,
        themes=list(mention.themes),
        region=mention.region,
        is_relevant=bool(mention.is_relevant),
        reasoning=mention.reasoning,
    )


async def persist_node(state: SovPipelineState) -> dict:
    """Filter to relevant mentions and bulk-insert into sov_mentions."""
    classified = state["classified_mentions"]
    if not classified:
        logger.info("sov_persist_skipped", reason="no_classified")
        return {"persisted_count": 0, "errors": []}

    run_at = state["run_at"]
    relevant = [m for m in classified if m.is_relevant]
    irrelevant_dropped = len(classified) - len(relevant)

    rows = [_to_row(m, run_at) for m in relevant]

    errors: list[str] = []
    submitted = 0
    try:
        submitted = insert_sov_mentions(rows)
    except Exception as exc:
        errors.append(f"persist:bulk_insert:{exc}")

    logger.info(
        "sov_persist_done",
        classified=len(classified),
        irrelevant_dropped=irrelevant_dropped,
        submitted=submitted,
        errors=len(errors),
    )

    return {
        "persisted_count": submitted,
        "errors": errors,
    }
