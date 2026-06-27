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

import re
from datetime import date, datetime, timedelta
from typing import Any

import structlog

from app.agents.sov.state import Mention, SovPipelineState
from app.rag.supabase_client import get_supabase

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

# "6 hours ago", "2 days ago", "1 week ago", "3 months ago", "1 year ago"
_RELATIVE_RE = re.compile(
    r"^(\d+)\s+(hour|day|week|month|year)s?\s+ago$",
    re.IGNORECASE,
)


def _parse_relative_ago(raw: str, reference: date) -> date | None:
    """Parse 'N units ago' relative to `reference`. None if no match.

    Months and years are approximated as 30 / 365 days — fine for monthly
    bucketing where day-of-month does not matter.
    """
    match = _RELATIVE_RE.match(raw.strip())
    if not match:
        return None
    n = int(match.group(1))
    unit = match.group(2).lower()
    if unit == "hour":
        return reference  # within the same day in practice
    if unit == "day":
        return reference - timedelta(days=n)
    if unit == "week":
        return reference - timedelta(weeks=n)
    if unit == "month":
        return reference - timedelta(days=30 * n)
    if unit == "year":
        return reference - timedelta(days=365 * n)
    return None


def _parse_news_date(raw: Any, reference: date | None = None) -> date | None:
    """Parse a news published_date string in one of several formats.

    Supported:
      - ISO timestamps: '2026-04-10T10:00:00Z', '2026-04-10T10:00:00+00:00'
      - Plain ISO date: '2026-04-10'
      - Short English:  'Apr 10, 2026' / 'Nov 11, 2025'
      - Relative:       '6 hours ago' / '2 days ago' / '1 month ago'
                        (needs `reference`, otherwise unparseable)

    Returns None when no format matches.
    """
    if not isinstance(raw, str) or not raw:
        return None
    raw = raw.strip()

    # ISO timestamp or date
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        pass

    # 'Apr 10, 2026' / 'Nov 11, 2025'
    try:
        return datetime.strptime(raw, "%b %d, %Y").date()
    except ValueError:
        pass

    # '6 hours ago' etc — needs a reference point
    if reference is not None:
        return _parse_relative_ago(raw, reference)

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

def _build_news_mention(
    item: dict,
    company: str,
    reference_date: date | None = None,
) -> Mention | None:
    """Convert one news item dict to a Mention. Returns None on missing essentials.

    `reference_date` is the snapshot's run date — used to resolve relative
    published_date strings like '6 hours ago'.
    """
    url = item.get("url")
    if not url:
        return None

    pub_date = _parse_news_date(item.get("published_date"), reference=reference_date)
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

    row = rows[0]
    reference_date = _parse_run_at(row.get("run_at"))
    items = (row.get("data") or {}).get("news", [])
    mentions = [
        m for item in items
        if (m := _build_news_mention(item, company, reference_date)) is not None
    ]
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
