"""Events report data loader.

Reads research_snapshots where node='events'. Each snapshot contains
four event source arrays which are merged into a single list.
"""

import structlog
from app.rag.supabase_client import get_supabase
from .base import BaseReportLoader

logger = structlog.get_logger(__name__)


class EventsReportLoader(BaseReportLoader):

    async def fetch(self) -> dict:
        db = get_supabase()

        comp_query = db.table("competitors").select("domain, name").eq("active", True)
        if self.companies:
            comp_query = comp_query.in_("domain", self.companies)
        comp_resp = comp_query.execute()
        competitors = comp_resp.data or []
        name_by_domain = {c["domain"]: c["name"] for c in competitors}
        domains = list(name_by_domain.keys())

        if not domains:
            return {"companies": []}

        snap_resp = (
            db.table("research_snapshots")
            .select("company, run_at, data")
            .eq("node", "events")
            .in_("company", domains)
            .order("run_at", desc=True)
            .execute()
        )
        rows = snap_resp.data or []

        # Keep only the latest snapshot per company
        latest: dict[str, dict] = {}
        for row in rows:
            if row["company"] not in latest:
                latest[row["company"]] = row

        companies_data = []
        for domain, row in latest.items():
            data = row["data"]
            all_events = (
                data.get("website_events", [])
                + data.get("luma_events", [])
                + data.get("meetup_events", [])
                + data.get("reported_events", [])
            )
            companies_data.append({
                "company": name_by_domain.get(domain, domain),
                "domain": domain,
                "run_at": str(row["run_at"]),
                "event_count": len(all_events),
                "events": [
                    {
                        "name": e.get("name") or e.get("title"),
                        "event_date": e.get("event_date"),
                        "location": e.get("location"),
                        "event_topic": e.get("event_topic"),
                        "summary": (
                            e.get("summary")
                            if isinstance(e.get("summary"), str)
                            else " ".join(e.get("summary") or [])
                        ),
                        "source_type": e.get("source_type"),
                        "attendees": e.get("attendees"),
                    }
                    for e in all_events[:20]
                ],
            })

        return {"companies": companies_data}