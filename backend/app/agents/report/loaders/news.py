"""News report data loader.

Reads research_snapshots where node='news', returns the latest article
list per company — mirrors GET /news but simplified for report generation.
"""

import structlog
from app.rag.supabase_client import get_supabase
from .base import BaseReportLoader

logger = structlog.get_logger(__name__)


class NewsReportLoader(BaseReportLoader):

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
            .eq("node", "news")
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
            articles = row["data"].get("news", [])
            companies_data.append({
                "company": name_by_domain.get(domain, domain),
                "domain": domain,
                "run_at": str(row["run_at"]),
                "article_count": len(articles),
                "articles": [
                    {
                        "title": a.get("title") or a.get("heading"),
                        "summary": a.get("summary"),
                        "published_date": a.get("published_date"),
                        "source_type": a.get("source_type"),
                        "url": a.get("url"),
                    }
                    for a in articles[:20]
                ],
            })

        return {"companies": companies_data}