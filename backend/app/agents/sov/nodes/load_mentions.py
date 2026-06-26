"""backend/app/agents/sov/nodes/load_mentions.py

Phase 1 of the SoV pipeline: read raw research data, build Mention objects,
filter out URLs that are already persisted in sov_mentions.

Sources in MVP:
- News:  research_snapshots WHERE node='news'   → data.news[]
- SEO:   research_snapshots WHERE node='seogeo' → data.seo[]

Per competitor we use only the latest snapshot (order by run_at desc, limit 1).
Older snapshots are ignored — the dashboard reflects the freshest research run.

Mentions whose (company, source_type, url) already exists in sov_mentions are
dropped here so we don't pay for re-classifying them with the LLM. The natural
key in sov_mentions would catch duplicates at write time anyway, but pre-
filtering is cheaper.
"""

from datetime import date, datetime
from typing import Any

import structlog

from app.agents.sov.state import Mention, SovPipelineState
from app.rag.supabase_client import get_supabase

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

def _parse_news_date(raw: Any) -> date | None:
    """News published_date comes in as a string. Accept ISO and plain YYYY-MM-DD."""
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_run_at(raw: Any) -> date:
    """research_snapshots.run_at is an ISO timestamp. Fall back to today if unparseable."""
    if isinstance(raw, str) and raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        except ValueError:
            pass
    return datetime.now().date()


# ---------------------------------------------------------------------------
# Per-item converters
# ---------------------------------------------------------------------------

def _build_news_mention(item: dict, company: str) -> Mention | None:
    """Convert one news item dict to a Mention. Returns None on missing essentials."""
    url = item.get("url")
    if not url:
        return None

    pub_date = _parse_news_date(item.get("published_date"))
    if pub_date is None:
        return None  # without a date the mention can't be bucketed for trends

    title = item.get("title") or item.get("heading")
    if not title:
        return None

    return Mention(
        company=company,
        source_type="news",
        source=item.get("source_type") or "unknown",
        title=title,
        content=item.get("text") or item.get("summary"),
        date=pub_date,
        month_bucket=pub_date.strftime("%Y-%m"),
        url=url,
        language=None,
    )


def _build_seo_mention(item: dict, company: str, run_date: date) -> Mention | None:
    """Convert one SEO keyword sighting to a Mention.

    Only sightings where the competitor actually ranks (company_mentioned=true)
    become Mentions — the others mean "Google did not return this competitor"
    and are not visibility for SoV.
    """
    if not item.get("company_mentioned"):
        return None

    url = item.get("link") or item.get("url")
    if not url:
        return None

    keyword = item.get("keyword", "")
    position = item.get("position")
    position_str = f" (position {position})" if position is not None else ""

    return Mention(
        company=company,
        source_type="seo",
        source="google_serp",
        title=f"SEO ranking: {keyword}",
        content=f"Google ranked {company} for '{keyword}'{position_str}.",
        date=run_date,
        month_bucket=run_date.strftime("%Y-%m"),
        url=url,
        language=None,
    )


# ---------------------------------------------------------------------------
# Per-source loaders
# ---------------------------------------------------------------------------

def _load_news_for_company(client, company: str) -> list[Mention]:
    """Latest news snapshot → list[Mention]."""
    try:
        resp = (
            client.table("research_snapshots")
            .select("data, run_at")
            .eq("node", "news")
            .eq("company", company)
            .order("run_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.error("sov_load_news_failed", company=company, error=str(exc))
        return []

    rows = resp.data or []
    if not rows:
        return []

    items = (rows[0].get("data") or {}).get("news", [])
    mentions = [m for item in items if (m := _build_news_mention(item, company)) is not None]
    logger.info(
        "sov_load_news_done",
        company=company,
        raw_items=len(items),
        mentions=len(mentions),
    )
    return mentions


def _load_seo_for_company(client, company: str) -> list[Mention]:
    """Latest seogeo snapshot → list[Mention] (only seo sightings, only mentioned ones)."""
    try:
        resp = (
            client.table("research_snapshots")
            .select("data, run_at")
            .eq("node", "seogeo")
            .eq("company", company)
            .order("run_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.error("sov_load_seo_failed", company=company, error=str(exc))
        return []

    rows = resp.data or []
    if not rows:
        return []

    row = rows[0]
    run_date = _parse_run_at(row.get("run_at"))
    items = (row.get("data") or {}).get("seo", [])
    mentions = [
        m for item in items if (m := _build_seo_mention(item, company, run_date)) is not None
    ]
    logger.info(
        "sov_load_seo_done",
        company=company,
        raw_items=len(items),
        mentions=len(mentions),
    )
    return mentions


# ---------------------------------------------------------------------------
# Pre-filter: skip URLs already in sov_mentions
# ---------------------------------------------------------------------------

def _filter_already_persisted(client, mentions: list[Mention]) -> list[Mention]:
    """Drop mentions whose (company, source_type, url) triple is already stored.

    On query failure we fall through with the unfiltered list — the
    ON CONFLICT DO NOTHING in sov_repository will still prevent duplicates at
    write time, we just pay for unnecessary LLM calls.
    """
    if not mentions:
        return []

    urls = list({m.url for m in mentions})

    try:
        resp = (
            client.table("sov_mentions")
            .select("company, source_type, url")
            .in_("url", urls)
            .execute()
        )
    except Exception as exc:
        logger.error("sov_prefilter_failed", error=str(exc))
        return mentions

    seen: set[tuple[str, str, str]] = {
        (row["company"], row["source_type"], row["url"]) for row in (resp.data or [])
    }

    new = [m for m in mentions if (m.company, m.source_type, m.url) not in seen]
    logger.info(
        "sov_prefilter_done",
        candidates=len(mentions),
        already_persisted=len(mentions) - len(new),
        remaining=len(new),
    )
    return new


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------

async def load_mentions_node(state: SovPipelineState) -> dict:
    """Read news + SEO for every competitor, return the not-yet-persisted ones.

    Returns a partial state update:
      candidate_mentions: list[Mention]
      errors:             list[str]   (per-company / per-source failures)
    """
    client = get_supabase()
    companies = state["companies"]

    all_mentions: list[Mention] = []
    errors: list[str] = []

    for company in companies:
        try:
            all_mentions.extend(_load_news_for_company(client, company))
        except Exception as exc:
            errors.append(f"news:{company}:{exc}")

        try:
            all_mentions.extend(_load_seo_for_company(client, company))
        except Exception as exc:
            errors.append(f"seo:{company}:{exc}")

    candidates = _filter_already_persisted(client, all_mentions)

    logger.info(
        "sov_load_mentions_node_done",
        companies=len(companies),
        loaded=len(all_mentions),
        new_candidates=len(candidates),
        errors=len(errors),
    )

    return {
        "candidate_mentions": candidates,
        "errors": errors,
    }
