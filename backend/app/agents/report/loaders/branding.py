"""Branding report data loader.

Branding analysis is cross-competitor by design — visualbranding_snapshots
has no company column. We read the latest row per node and pass the full
data payload to the prompt builder.
"""

import structlog
from app.rag.supabase_client import get_supabase
from .base import BaseReportLoader

logger = structlog.get_logger(__name__)

BRANDING_NODES = ["trends", "colors", "fonts", "images"]


class BrandingReportLoader(BaseReportLoader):

    async def fetch(self) -> dict:
        db = get_supabase()

        snap_resp = (
            db.table("visualbranding_snapshots")
            .select("node, run_at, data")
            .in_("node", BRANDING_NODES)
            .order("run_at", desc=True)
            .execute()
        )
        rows = snap_resp.data or []

        # Keep only the latest row per node
        latest: dict[str, dict] = {}
        for row in rows:
            if row["node"] not in latest:
                latest[row["node"]] = row

        return {
            node: {
                "run_at": str(row["run_at"]),
                "data": row["data"],
            }
            for node, row in latest.items()
        }