"""Brand Intelligence API router.

GET /brand/geo-intelligence/{company}
    Zone 1 (KPI tiles) and Zone 2 (trend charts).

GET /brand/geo-intelligence/{company}/share-of-voice
    Zone 3 (AI Share of Voice) — per-tier competitive mention rates.

GET /brand/geo-intelligence/{company}/strategic-maps
    Zone 4 (peer network + territory heatmap).

All endpoints require a valid JWT via Authorization: Bearer <token>.
"""

import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.auth.dependencies import require_auth
from app.rag.supabase_client import get_supabase

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/brand", tags=["brand"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class KpiDeltas(BaseModel):
    visibility_pct: float | None
    geo_score: float | None
    active_recommendation_pct: float | None
    gap_count: int | None


class KpiBlock(BaseModel):
    visibility_pct: float
    geo_score: float
    active_recommendation_pct: float
    gap_count: int
    deltas: KpiDeltas | None


class TrendPoint(BaseModel):
    run_at: datetime
    visibility_pct: float
    geo_score: float


class LlmComparisonPoint(BaseModel):
    llm: str
    mention_rate: float
    recommendation_rate: float


class LlmTrendPoint(BaseModel):
    run_at: datetime
    llm: str
    mention_rate: float


class TrendsBlock(BaseModel):
    series: list[TrendPoint]
    llm_series: list[LlmTrendPoint]
    llm_comparison: list[LlmComparisonPoint]


class GeoIntelligenceResponse(BaseModel):
    company: str
    latest_run_at: datetime
    kpis: KpiBlock
    trends: TrendsBlock
    available_llms: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _geo_score(mention_rate: float, recommendation_rate: float) -> float:
    """Composite GEO score on a 0–100 scale."""
    return round((mention_rate * 40) + (recommendation_rate * 60), 1)


def _compute_deltas(current: dict, previous: dict | None) -> KpiDeltas | None:
    if previous is None:
        return None
    cur_mr = current.get("mention_rate") or 0.0
    prev_mr = previous.get("mention_rate") or 0.0
    cur_rr = current.get("recommendation_rate") or 0.0
    prev_rr = previous.get("recommendation_rate") or 0.0
    cur_gap = current.get("gap_keyword_count") or 0
    prev_gap = previous.get("gap_keyword_count") or 0
    return KpiDeltas(
        visibility_pct=round(cur_mr - prev_mr, 4),
        geo_score=round(_geo_score(cur_mr, cur_rr) - _geo_score(prev_mr, prev_rr), 1),
        active_recommendation_pct=round(cur_rr - prev_rr, 4),
        gap_count=cur_gap - prev_gap,
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/geo-intelligence/{company}",
    response_model=GeoIntelligenceResponse,
)
async def get_geo_intelligence(
    company: str,
    llm: Annotated[str | None, Query(description="Filter KPI tiles to a specific LLM provider.")] = None,
    _: None = Depends(require_auth),
) -> GeoIntelligenceResponse:
    """Return GEO Intelligence dashboard data for Zone 1 and Zone 2.

    Reads from brand_geo_runs (all runs, ordered ascending for trend series)
    and brand_geo_sightings (latest run only, for LLM comparison + filter).

    Args:
        company: Company domain, e.g. "celonis.com".
        llm: Optional LLM name to filter Zone 1 KPI tiles. When set, KPIs are
            computed from sightings for that model only. Deltas are omitted
            in this view. Trend series always shows the aggregate.

    Raises:
        404: No pipeline runs found for this company.
        500: Unexpected database error.
    """
    db = get_supabase()

    try:
        runs_resp = (
            db.table("brand_geo_runs")
            .select(
                "run_at, mention_rate, recommendation_rate, gap_keyword_count"
            )
            .eq("company", company)
            .order("run_at", desc=False)
            .execute()
        )
    except Exception as exc:
        logger.error("geo_runs_query_failed", company=company, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query GEO run data.",
        )

    runs: list[dict] = runs_resp.data or []

    if not runs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No GEO Intelligence runs found for company '{company}'.",
        )

    latest = runs[-1]
    previous = runs[-2] if len(runs) >= 2 else None

    # ------------------------------------------------------------------
    # Fetch sightings for latest run — needed for LLM comparison and filter
    # ------------------------------------------------------------------
    try:
        sightings_resp = (
            db.table("brand_geo_sightings")
            .select("llm, mentioned, recommendation_strength")
            .eq("company", company)
            .eq("run_at", latest["run_at"])
            .execute()
        )
    except Exception as exc:
        logger.error("geo_sightings_query_failed", company=company, error=str(exc))
        sightings_resp = None

    sightings: list[dict] = (sightings_resp.data if sightings_resp else None) or []

    # LLMs present in the latest run — for frontend filter pills
    available_llms: list[str] = sorted({row.get("llm") or "unknown" for row in sightings})

    # ------------------------------------------------------------------
    # Zone 1 — KPIs
    # When llm filter is active: compute from sightings (no deltas).
    # Without filter: read from brand_geo_runs aggregate (with deltas).
    # ------------------------------------------------------------------
    if llm:
        llm_rows = [row for row in sightings if row.get("llm") == llm]
        total_llm = len(llm_rows) or 1
        mr = sum(1 for r in llm_rows if r.get("mentioned")) / total_llm
        rr = sum(
            1 for r in llm_rows
            if r.get("recommendation_strength") in ("recommended", "organic")
        ) / total_llm
        gap = sum(1 for r in llm_rows if not r.get("mentioned"))
        kpis = KpiBlock(
            visibility_pct=mr,
            geo_score=_geo_score(mr, rr),
            active_recommendation_pct=rr,
            gap_count=gap,
            deltas=None,
        )
    else:
        # Guard: recommendation_rate may be null in older runs (pre-migration 007)
        latest_rec_rate = latest.get("recommendation_rate") or 0.0
        prev_rec_rate = (previous.get("recommendation_rate") or 0.0) if previous else 0.0
        if previous:
            previous = {**previous, "recommendation_rate": prev_rec_rate}
        kpis = KpiBlock(
            visibility_pct=latest["mention_rate"] or 0.0,
            geo_score=_geo_score(latest["mention_rate"] or 0.0, latest_rec_rate),
            active_recommendation_pct=latest_rec_rate,
            gap_count=latest["gap_keyword_count"] or 0,
            deltas=_compute_deltas(
                {**latest, "recommendation_rate": latest_rec_rate},
                previous,
            ),
        )

    # ------------------------------------------------------------------
    # Zone 2a — Aggregate trend series (from brand_geo_runs)
    # ------------------------------------------------------------------
    series = [
        TrendPoint(
            run_at=r["run_at"],
            visibility_pct=r["mention_rate"] or 0.0,
            geo_score=_geo_score(
                r["mention_rate"] or 0.0,
                r.get("recommendation_rate") or 0.0,
            ),
        )
        for r in runs
    ]

    # ------------------------------------------------------------------
    # Zone 2a — Per-LLM trend lines (from sightings across all runs)
    # One extra query; acceptable since run count is small.
    # ------------------------------------------------------------------
    llm_series: list[LlmTrendPoint] = []
    try:
        all_sightings_resp = (
            db.table("brand_geo_sightings")
            .select("run_at, llm, mentioned")
            .eq("company", company)
            .execute()
        )
        all_sightings: list[dict] = (all_sightings_resp.data or [])
        run_llm_totals: dict[tuple[str, str], int] = defaultdict(int)
        run_llm_mentions: dict[tuple[str, str], int] = defaultdict(int)
        for row in all_sightings:
            key = (row["run_at"], row.get("llm") or "unknown")
            run_llm_totals[key] += 1
            if row.get("mentioned"):
                run_llm_mentions[key] += 1
        llm_series = [
            LlmTrendPoint(
                run_at=run_at,
                llm=llm_name,
                mention_rate=round(run_llm_mentions[(run_at, llm_name)] / total, 4),
            )
            for (run_at, llm_name), total in run_llm_totals.items()
        ]
    except Exception as exc:
        logger.warning("geo_llm_trend_failed", company=company, error=str(exc))

    # ------------------------------------------------------------------
    # Zone 2b — LLM comparison (latest run, always all LLMs + aggregate)
    # ------------------------------------------------------------------
    llm_totals: Counter = Counter()
    llm_mentions: Counter = Counter()
    llm_recs: Counter = Counter()
    for row in sightings:
        llm_name = row.get("llm") or "unknown"
        llm_totals[llm_name] += 1
        if row.get("mentioned"):
            llm_mentions[llm_name] += 1
        if row.get("recommendation_strength") in ("recommended", "organic"):
            llm_recs[llm_name] += 1

    llm_comparison: list[LlmComparisonPoint] = [
        LlmComparisonPoint(
            llm=llm_name,
            mention_rate=round(llm_mentions[llm_name] / total, 4) if total else 0.0,
            recommendation_rate=round(llm_recs[llm_name] / total, 4) if total else 0.0,
        )
        for llm_name, total in llm_totals.items()
    ]

    # Append aggregate bar — pooled across all LLMs in the latest run
    total_all = sum(llm_totals.values())
    if total_all > 0:
        llm_comparison.append(LlmComparisonPoint(
            llm="aggregate",
            mention_rate=round(sum(llm_mentions.values()) / total_all, 4),
            recommendation_rate=round(sum(llm_recs.values()) / total_all, 4),
        ))

    return GeoIntelligenceResponse(
        company=company,
        latest_run_at=latest["run_at"],
        kpis=kpis,
        trends=TrendsBlock(
            series=series,
            llm_series=llm_series,
            llm_comparison=llm_comparison,
        ),
        available_llms=available_llms,
    )


# ---------------------------------------------------------------------------
# Zone 3 — Strategic Maps
# ---------------------------------------------------------------------------

class PeerNode(BaseModel):
    id: str
    is_target: bool
    weight: int


class PeerLink(BaseModel):
    source: str
    target: str
    weight: int
    distance: int


class PeerNetworkBlock(BaseModel):
    nodes: list[PeerNode]
    links: list[PeerLink]
    primary_peer_group: list[str]


class HeatmapCell(BaseModel):
    x: str
    y: int


class HeatmapRow(BaseModel):
    id: str
    data: list[HeatmapCell]


class TerritoryOwner(BaseModel):
    tier: str
    competitors: list[dict]


class TerritoryMapBlock(BaseModel):
    rows: list[HeatmapRow]
    owned_territories: list[str]
    contested_territories: list[str]
    absent_territories: list[str]
    territory_owners: list[TerritoryOwner]


class StrategicMapsResponse(BaseModel):
    company: str
    run_at: str
    peer_network: PeerNetworkBlock
    territory_map: TerritoryMapBlock


_STRENGTH_ORDER = ["listed", "attributed", "recommended", "organic", "absent"]
_TIER_ORDER = ["brand_category", "use_case", "competitor_trigger"]


@router.get(
    "/geo-intelligence/{company}/strategic-maps",
    response_model=StrategicMapsResponse,
)
async def get_strategic_maps(
    company: str,
    llm: Annotated[str | None, Query()] = None,
    _: None = Depends(require_auth),
) -> StrategicMapsResponse:
    """Return Zone 3 strategic map data: peer network and territory heatmap.

    Reads the latest run from brand_geo_runs (for synthesis metadata) and
    brand_geo_sightings (for per-keyword signals). All aggregation happens
    in Python — Supabase client has no GROUP BY or array unnesting.

    Args:
        company: Company domain, e.g. "celonis.com".

    Raises:
        404: No pipeline runs found for this company.
        500: Unexpected database error.
    """
    db = get_supabase()

    # Fetch latest run metadata (territories + peer group from synthesis)
    try:
        run_resp = (
            db.table("brand_geo_runs")
            .select(
                "run_at, primary_peer_group, owned_territories, "
                "contested_territories, absent_territories"
            )
            .eq("company", company)
            .order("run_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.error("geo_run_query_failed", company=company, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query GEO run data.",
        )

    if not run_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No GEO Intelligence runs found for company '{company}'.",
        )

    run = run_resp.data[0]

    # Fetch sightings for the latest run, optionally filtered by LLM
    try:
        q = (
            db.table("brand_geo_sightings")
            .select("tier, mentioned, recommendation_strength, co_mentioned_companies")
            .eq("company", company)
            .eq("run_at", run["run_at"])
        )
        if llm:
            q = q.eq("llm", llm)
        sightings_resp = q.execute()
    except Exception as exc:
        logger.error("geo_sightings_query_failed", company=company, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query GEO sightings data.",
        )

    sightings: list[dict] = sightings_resp.data or []

    # ------------------------------------------------------------------
    # Peer Network — aggregate co_mentioned_companies across all sightings
    # ------------------------------------------------------------------
    co_mention_counts: Counter = Counter()
    for row in sightings:
        raw = row.get("co_mentioned_companies")
        if not raw:
            continue
        companies = json.loads(raw) if isinstance(raw, str) else raw
        for c in companies:
            if c:
                co_mention_counts[c.strip()] += 1

    company_name = company.split(".")[0].capitalize()
    total_keywords = len(sightings)

    # Celonis weight = keywords where it was actually mentioned (not total keywords)
    celonis_mention_count = sum(1 for row in sightings if row.get("mentioned"))

    peer_nodes: list[PeerNode] = [
        PeerNode(id=company_name, is_target=True, weight=celonis_mention_count)
    ] + [
        PeerNode(id=name, is_target=False, weight=count)
        for name, count in co_mention_counts.most_common(15)
    ]

    # Distance: inversely proportional to co-mention frequency.
    # High weight → small distance (drawn closer to target in force graph).
    max_weight = max(co_mention_counts.values(), default=1)
    peer_links: list[PeerLink] = [
        PeerLink(
            source=company_name,
            target=name,
            weight=count,
            distance=max(30, round(200 * (1 - count / max_weight)) + 30),
        )
        for name, count in co_mention_counts.most_common(15)
        if count > 0
    ]

    primary_peer_group = run.get("primary_peer_group") or []
    if isinstance(primary_peer_group, str):
        primary_peer_group = json.loads(primary_peer_group)

    # ------------------------------------------------------------------
    # Territory Heatmap — pivot tier × recommendation_strength
    # "absent" = mentioned=false (no strength value)
    # ------------------------------------------------------------------
    pivot: dict[str, Counter] = {tier: Counter() for tier in _TIER_ORDER}
    absent_by_tier: dict[str, list[list[str]]] = {tier: [] for tier in _TIER_ORDER}

    for row in sightings:
        tier = row.get("tier") or "unknown"
        if tier not in pivot:
            continue
        if not row.get("mentioned"):
            pivot[tier]["absent"] += 1
            raw = row.get("co_mentioned_companies")
            if raw:
                companies = json.loads(raw) if isinstance(raw, str) else raw
                absent_by_tier[tier].append(companies)
        else:
            strength = row.get("recommendation_strength") or "listed"
            pivot[tier][strength] += 1

    heatmap_rows = [
        HeatmapRow(
            id=tier,
            data=[
                HeatmapCell(x=strength, y=pivot[tier].get(strength, 0))
                for strength in _STRENGTH_ORDER
            ],
        )
        for tier in _TIER_ORDER
    ]

    # Territory owners — dominant competitor per tier in absent keywords
    territory_owners: list[TerritoryOwner] = []
    for tier in _TIER_ORDER:
        if not absent_by_tier[tier]:
            continue
        competitor_counts: Counter = Counter()
        for companies in absent_by_tier[tier]:
            for c in companies:
                if c:
                    competitor_counts[c.strip()] += 1
        if competitor_counts:
            territory_owners.append(
                TerritoryOwner(
                    tier=tier,
                    competitors=[
                        {"name": name, "count": count}
                        for name, count in competitor_counts.most_common(3)
                    ],
                )
            )

    owned = run.get("owned_territories") or []
    contested = run.get("contested_territories") or []
    absent = run.get("absent_territories") or []
    for field in [owned, contested, absent]:
        if isinstance(field, str):
            field = json.loads(field)

    if isinstance(owned, str):
        owned = json.loads(owned)
    if isinstance(contested, str):
        contested = json.loads(contested)
    if isinstance(absent, str):
        absent = json.loads(absent)

    return StrategicMapsResponse(
        company=company,
        run_at=run["run_at"],
        peer_network=PeerNetworkBlock(
            nodes=peer_nodes,
            links=peer_links,
            primary_peer_group=primary_peer_group,
        ),
        territory_map=TerritoryMapBlock(
            rows=heatmap_rows,
            owned_territories=owned,
            contested_territories=contested,
            absent_territories=absent,
            territory_owners=territory_owners,
        ),
    )


# ---------------------------------------------------------------------------
# Zone 3 — AI Share of Voice
# ---------------------------------------------------------------------------

_TIER_LABELS: dict[str, str] = {
    "brand_category": "Brand & Category",
    "use_case": "Use Case / Problem",
    "competitor_trigger": "Competitor Trigger",
}

_SOV_TOP_N = 5


class SovEntry(BaseModel):
    company: str
    is_target: bool
    mention_count: int
    mention_rate: float


class SovTier(BaseModel):
    tier: str
    label: str
    total_keywords: int
    entries: list[SovEntry]


class ShareOfVoiceResponse(BaseModel):
    company: str
    run_at: str
    tiers: list[SovTier]


@router.get(
    "/geo-intelligence/{company}/share-of-voice",
    response_model=ShareOfVoiceResponse,
)
async def get_share_of_voice(
    company: str,
    llm: Annotated[str | None, Query()] = None,
    _: None = Depends(require_auth),
) -> ShareOfVoiceResponse:
    """Return AI Share of Voice per keyword tier for Zone 3.

    For each tier (brand_category, use_case, competitor_trigger):
    - Target company mention rate: rows where mentioned=true / total rows in tier
    - Competitor mention rate: co_mentioned_companies frequency / total rows in tier
    - Returns top 5 companies per tier including the target.

    Args:
        company: Company domain, e.g. "celonis.com".

    Raises:
        404: No pipeline runs found for this company.
        500: Unexpected database error.
    """
    db = get_supabase()

    # Get latest run_at
    try:
        run_resp = (
            db.table("brand_geo_runs")
            .select("run_at")
            .eq("company", company)
            .order("run_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.error("geo_run_query_failed", company=company, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query GEO run data.",
        )

    if not run_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No GEO Intelligence runs found for company '{company}'.",
        )

    latest_run_at = run_resp.data[0]["run_at"]

    # Fetch sightings for latest run — only fields needed for SoV
    try:
        q = (
            db.table("brand_geo_sightings")
            .select("tier, mentioned, co_mentioned_companies, llm")
            .eq("company", company)
            .eq("run_at", latest_run_at)
        )
        if llm:
            q = q.eq("llm", llm)
        sightings_resp = q.execute()
    except Exception as exc:
        logger.error("geo_sightings_query_failed", company=company, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query GEO sightings data.",
        )

    sightings: list[dict] = sightings_resp.data or []
    company_name = company.split(".")[0].capitalize()

    # When filtered to a single LLM, n_llms=1 → no normalisation needed.
    # When aggregated, divide by n_llms so badge counts stay per-keyword.
    n_llms = len({row.get("llm") for row in sightings if row.get("llm")}) or 1

    # ------------------------------------------------------------------
    # Aggregate per tier
    # tier_totals:       total sighting count per tier (= keywords × n_llms)
    # target_counts:     mentions across all LLMs per tier
    # competitor_counts: co-mention frequency per competitor per tier
    # ------------------------------------------------------------------
    tier_totals: Counter = Counter()
    target_counts: Counter = Counter()
    competitor_counts: dict[str, Counter] = {t: Counter() for t in _TIER_ORDER}

    for row in sightings:
        tier = row.get("tier") or "unknown"
        if tier not in _TIER_ORDER:
            continue

        tier_totals[tier] += 1

        if row.get("mentioned"):
            target_counts[tier] += 1

        raw = row.get("co_mentioned_companies")
        if raw:
            companies = json.loads(raw) if isinstance(raw, str) else raw
            for c in companies:
                if c:
                    competitor_counts[tier][c.strip()] += 1

    # ------------------------------------------------------------------
    # Build response — one SovTier per tier, top N entries
    # Normalise counts by n_llms so badges show per-keyword figures, not
    # per-(keyword × LLM) figures. mention_rate is computed after normalising
    # so the denominator stays consistent with total_keywords.
    # ------------------------------------------------------------------
    tiers: list[SovTier] = []

    for tier in _TIER_ORDER:
        raw_total = tier_totals[tier]
        if raw_total == 0:
            continue

        total_keywords = round(raw_total / n_llms)
        norm_target = round(target_counts[tier] / n_llms)

        # Target entry always included
        target_entry = SovEntry(
            company=company_name,
            is_target=True,
            mention_count=norm_target,
            mention_rate=round(norm_target / total_keywords, 4) if total_keywords else 0.0,
        )

        # Top N-1 competitors (excluding target name if it appears in co-mentions)
        competitor_entries = [
            SovEntry(
                company=name,
                is_target=False,
                mention_count=round(count / n_llms),
                mention_rate=round((count / n_llms) / total_keywords, 4) if total_keywords else 0.0,
            )
            for name, count in competitor_counts[tier].most_common(_SOV_TOP_N - 1)
            if name.lower() != company_name.lower()
        ]

        # Sort all entries by mention_rate descending
        all_entries = sorted(
            [target_entry] + competitor_entries,
            key=lambda e: e.mention_rate,
            reverse=True,
        )

        tiers.append(
            SovTier(
                tier=tier,
                label=_TIER_LABELS.get(tier, tier),
                total_keywords=total_keywords,
                entries=all_entries,
            )
        )

    return ShareOfVoiceResponse(
        company=company,
        run_at=latest_run_at,
        tiers=tiers,
    )


# ---------------------------------------------------------------------------
# Zone 5 — Deep Dive
# ---------------------------------------------------------------------------

class AlertCards(BaseModel):
    critical_gap: str | None
    framing_gap: str | None
    counter_positioning: str | None


class LlmKeywordResult(BaseModel):
    llm: str
    mentioned: bool
    framing: str | None
    recommendation_strength: str | None
    exact_quote: str | None


class KeywordRow(BaseModel):
    keyword: str
    tier: str
    mentioned: bool
    framing: str | None
    recommendation_strength: str | None
    use_case_context: str | None
    counter_positioning: str | None
    exact_quote: str | None
    per_llm: list[LlmKeywordResult]


class DeepDiveResponse(BaseModel):
    company: str
    run_at: str
    alerts: AlertCards
    keyword_rows: list[KeywordRow]
    full_briefing: str | None


@router.get(
    "/geo-intelligence/{company}/deep-dive",
    response_model=DeepDiveResponse,
)
async def get_deep_dive(
    company: str,
    llm: Annotated[str | None, Query(description="Filter keyword rows to a specific LLM provider.")] = None,
    _: None = Depends(require_auth),
) -> DeepDiveResponse:
    """Return Zone 5 deep dive data: alert cards, keyword table, full briefing.

    Alert cards and full briefing come from brand_geo_runs (one read).
    Keyword rows come from brand_geo_sightings for the latest run (one read).

    Args:
        company: Company domain, e.g. "celonis.com".

    Raises:
        404: No pipeline runs found for this company.
        500: Unexpected database error.
    """
    db = get_supabase()

    # Fetch latest run — alerts + full briefing
    try:
        run_resp = (
            db.table("brand_geo_runs")
            .select("run_at, critical_gap, framing_gap, top_counter_positioning, narrative")
            .eq("company", company)
            .order("run_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.error("geo_run_query_failed", company=company, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query GEO run data.",
        )

    if not run_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No GEO Intelligence runs found for company '{company}'.",
        )

    run = run_resp.data[0]

    # Fetch keyword rows for latest run (always all LLMs — per_llm needs them)
    try:
        query = (
            db.table("brand_geo_sightings")
            .select(
                "keyword, tier, llm, mentioned, framing, recommendation_strength, "
                "use_case_context, counter_positioning, context"
            )
            .eq("company", company)
            .eq("run_at", run["run_at"])
            .order("tier")
            .order("keyword")
        )
        if llm:
            query = query.eq("llm", llm)
        sightings_resp = query.execute()
    except Exception as exc:
        logger.error("geo_sightings_query_failed", company=company, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query GEO sightings data.",
        )

    sightings: list[dict] = sightings_resp.data or []

    _strength_rank = {"organic": 4, "recommended": 3, "attributed": 2, "listed": 1}

    if llm:
        # Single LLM tab: flat rows, per_llm empty
        keyword_rows = [
            KeywordRow(
                keyword=row["keyword"],
                tier=row.get("tier") or "unknown",
                mentioned=row.get("mentioned") or False,
                framing=row.get("framing"),
                recommendation_strength=row.get("recommendation_strength"),
                use_case_context=row.get("use_case_context"),
                counter_positioning=row.get("counter_positioning"),
                exact_quote=row.get("context"),
                per_llm=[],
            )
            for row in sightings
        ]
    else:
        # All LLMs: group by keyword, build aggregate row + per_llm sub-rows
        # run_llms determines which LLMs appear (for dimmed "not mentioned" rows)
        run_llms: list[str] = sorted({row.get("llm") or "unknown" for row in sightings})

        keyword_groups: dict[str, list[dict]] = defaultdict(list)
        for row in sightings:
            keyword_groups[row["keyword"]].append(row)

        keyword_rows = []
        for keyword, rows in keyword_groups.items():
            # Best aggregate row
            best = rows[0]
            for row in rows[1:]:
                if row.get("mentioned") and not best.get("mentioned"):
                    best = row
                elif row.get("mentioned") == best.get("mentioned"):
                    nr = _strength_rank.get(row.get("recommendation_strength") or "", 0)
                    cr = _strength_rank.get(best.get("recommendation_strength") or "", 0)
                    if nr > cr:
                        best = row

            # per_llm: ALL LLMs in this run — non-mentioned ones show as dimmed
            llm_map = {r.get("llm") or "unknown": r for r in rows}
            per_llm = [
                LlmKeywordResult(
                    llm=l,
                    mentioned=llm_map[l].get("mentioned") or False if l in llm_map else False,
                    framing=llm_map[l].get("framing") if l in llm_map else None,
                    recommendation_strength=(
                        llm_map[l].get("recommendation_strength") if l in llm_map else None
                    ),
                    exact_quote=llm_map[l].get("context") if l in llm_map else None,
                )
                for l in run_llms
            ]

            keyword_rows.append(KeywordRow(
                keyword=keyword,
                tier=best.get("tier") or "unknown",
                mentioned=any(r.get("mentioned") for r in rows),
                framing=best.get("framing"),
                recommendation_strength=best.get("recommendation_strength"),
                use_case_context=best.get("use_case_context"),
                counter_positioning=best.get("counter_positioning"),
                exact_quote=best.get("context"),
                per_llm=per_llm,
            ))

        tier_order = {"brand_category": 0, "use_case": 1, "competitor_trigger": 2}
        keyword_rows.sort(key=lambda r: (tier_order.get(r.tier, 99), r.keyword))

    return DeepDiveResponse(
        company=company,
        run_at=run["run_at"],
        alerts=AlertCards(
            critical_gap=run.get("critical_gap"),
            framing_gap=run.get("framing_gap"),
            counter_positioning=run.get("top_counter_positioning"),
        ),
        keyword_rows=keyword_rows,
        full_briefing=run.get("narrative"),
    )
