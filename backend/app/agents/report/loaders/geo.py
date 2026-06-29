"""GEO Intelligence report data loader.

Reads brand_geo_runs for the latest synthesis row per company.
The geo_score formula mirrors the dashboard: mention_rate * 0.4 + recommendation_rate * 0.6.
"""

import structlog
from app.rag.supabase_client import get_supabase
from .base import BaseReportLoader

logger = structlog.get_logger(__name__)


class GeoReportLoader(BaseReportLoader):

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

        runs_resp = (
            db.table("brand_geo_runs")
            .select("*")
            .in_("company", domains)
            .order("run_at", desc=True)
            .execute()
        )
        runs = runs_resp.data or []

        # Keep only the latest run per company
        latest_runs: dict[str, dict] = {}
        for run in runs:
            if run["company"] not in latest_runs:
                latest_runs[run["company"]] = run

        companies_data = []
        for domain, run in latest_runs.items():
            mention_rate = run.get("mention_rate")
            recommendation_rate = run.get("recommendation_rate")
            geo_score = (
                round(mention_rate * 0.4 + recommendation_rate * 0.6, 3)
                if mention_rate is not None and recommendation_rate is not None
                else None
            )
            companies_data.append({
                "company": name_by_domain.get(domain, domain),
                "domain": domain,
                "run_at": str(run.get("run_at")),
                "mention_rate": mention_rate,
                "recommendation_rate": recommendation_rate,
                "geo_score": geo_score,
                "dominant_framing": run.get("dominant_framing"),
                "strongest_tier": run.get("strongest_tier"),
                "narrative": run.get("narrative"),
                "critical_gap": run.get("critical_gap"),
                "owned_territories": run.get("owned_territories"),
                "contested_territories": run.get("contested_territories"),
                "absent_territories": run.get("absent_territories"),
            })

        return {"companies": companies_data}