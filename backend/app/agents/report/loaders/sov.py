"""SOV (Share of Voice) report data loader.

Reads sov_mentions table — one row per article per company.
Groups by company and summarises theme distribution, region spread,
and relevance rate to give the prompt a compact, structured picture.
"""

import structlog
from app.rag.supabase_client import get_supabase
from .base import BaseReportLoader

logger = structlog.get_logger(__name__)


class SovReportLoader(BaseReportLoader):

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

        mentions_resp = (
            db.table("sov_mentions")
            .select("company, source_type, source, title, date, month_bucket, themes, region, is_relevant, reasoning")
            .in_("company", domains)
            .order("run_at", desc=True)
            .execute()
        )
        rows = mentions_resp.data or []

        # Group by company
        by_company: dict[str, list[dict]] = {}
        for row in rows:
            company = row["company"]
            if company not in by_company:
                by_company[company] = []
            by_company[company].append(row)

        companies_data = []
        for domain, mentions in by_company.items():
            total = len(mentions)
            relevant = [m for m in mentions if m.get("is_relevant")]

            # Theme frequency
            theme_counts: dict[str, int] = {}
            for m in relevant:
                for t in (m.get("themes") or []):
                    theme_counts[t] = theme_counts.get(t, 0) + 1

            # Region frequency
            region_counts: dict[str, int] = {}
            for m in relevant:
                region = m.get("region")
                if region:
                    region_counts[region] = region_counts.get(region, 0) + 1

            # Source type split
            news_count = sum(1 for m in mentions if m.get("source_type") == "news")
            seo_count = sum(1 for m in mentions if m.get("source_type") == "seo")

            # Most recent month bucket
            month_buckets = sorted(
                {m["month_bucket"] for m in mentions if m.get("month_bucket")},
                reverse=True,
            )

            companies_data.append({
                "company": name_by_domain.get(domain, domain),
                "domain": domain,
                "total_mentions": total,
                "relevant_mentions": len(relevant),
                "relevance_rate": round(len(relevant) / total, 3) if total > 0 else 0,
                "source_split": {"news": news_count, "seo": seo_count},
                "top_themes": dict(
                    sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)[:8]
                ),
                "region_distribution": region_counts,
                "latest_month": month_buckets[0] if month_buckets else None,
                "sample_mentions": [
                    {
                        "title": m.get("title"),
                        "date": str(m.get("date")),
                        "source": m.get("source"),
                        "themes": m.get("themes"),
                        "region": m.get("region"),
                        "reasoning": m.get("reasoning"),
                    }
                    for m in relevant[:10]
                ],
            })

        return {"companies": companies_data}