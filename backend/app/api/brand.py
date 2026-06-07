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
from collections import Counter
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
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


class TrendsBlock(BaseModel):
    series: list[TrendPoint]
    llm_comparison: list[LlmComparisonPoint]


class GeoIntelligenceResponse(BaseModel):
    company: str
    latest_run_at: datetime
    kpis: KpiBlock
    trends: TrendsBlock


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
    _: None = Depends(require_auth),
) -> GeoIntelligenceResponse:
    """Return GEO Intelligence dashboard data for Zone 1 and Zone 2.

    Reads from brand_geo_runs (all runs, ordered ascending for trend series)
    and brand_geo_sightings (latest run only, for LLM comparison).

    Args:
        company: Company domain, e.g. "celonis.com".

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

    # Guard: recommendation_rate may be null in older runs (pre-migration 007)
    latest_rec_rate = latest.get("recommendation_rate") or 0.0
    prev_rec_rate = (previous.get("recommendation_rate") or 0.0) if previous else 0.0

    if previous:
        previous = {**previous, "recommendation_rate": prev_rec_rate}

    # ------------------------------------------------------------------
    # Zone 1 — KPIs
    # ------------------------------------------------------------------
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
    # Zone 2a — Trend series (all runs)
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
    # Zone 2b — LLM comparison (latest run only, aggregated in Python)
    # Supabase client has no GROUP BY — fetch 30 rows, aggregate here.
    # ------------------------------------------------------------------
    try:
        sightings_resp = (
            db.table("brand_geo_sightings")
            .select("llm, mentioned")
            .eq("company", company)
            .eq("run_at", latest["run_at"])
            .execute()
        )
    except Exception as exc:
        logger.error("geo_sightings_query_failed", company=company, error=str(exc))
        sightings_resp = None

    sightings: list[dict] = (sightings_resp.data if sightings_resp else None) or []

    llm_totals: Counter = Counter()
    llm_mentions: Counter = Counter()
    for row in sightings:
        llm = row.get("llm") or "unknown"
        llm_totals[llm] += 1
        if row.get("mentioned"):
            llm_mentions[llm] += 1

    llm_comparison = [
        LlmComparisonPoint(
            llm=llm,
            mention_rate=round(llm_mentions[llm] / total, 4) if total else 0.0,
        )
        for llm, total in llm_totals.items()
    ]

    return GeoIntelligenceResponse(
        company=company,
        latest_run_at=latest["run_at"],
        kpis=kpis,
        trends=TrendsBlock(series=series, llm_comparison=llm_comparison),
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


_STRENGTH_ORDER = ["listed", "attributed", "recommended", "default", "absent"]
_TIER_ORDER = ["brand_category", "use_case", "competitor_trigger"]


@router.get(
    "/geo-intelligence/{company}/strategic-maps",
    response_model=StrategicMapsResponse,
)
async def get_strategic_maps(
    company: str,
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

    # Fetch all sightings for the latest run
    try:
        sightings_resp = (
            db.table("brand_geo_sightings")
            .select("tier, mentioned, recommendation_strength, co_mentioned_companies")
            .eq("company", company)
            .eq("run_at", run["run_at"])
            .execute()
        )
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

    peer_nodes: list[PeerNode] = [
        PeerNode(id=company_name, is_target=True, weight=total_keywords)
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
        sightings_resp = (
            db.table("brand_geo_sightings")
            .select("tier, mentioned, co_mentioned_companies")
            .eq("company", company)
            .eq("run_at", latest_run_at)
            .execute()
        )
    except Exception as exc:
        logger.error("geo_sightings_query_failed", company=company, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query GEO sightings data.",
        )

    sightings: list[dict] = sightings_resp.data or []
    company_name = company.split(".")[0].capitalize()

    # ------------------------------------------------------------------
    # Aggregate per tier
    # tier_totals:    total keyword count per tier
    # target_counts:  how many keywords target was mentioned in, per tier
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
    # ------------------------------------------------------------------
    tiers: list[SovTier] = []

    for tier in _TIER_ORDER:
        total = tier_totals[tier]
        if total == 0:
            continue

        # Target entry always included
        target_entry = SovEntry(
            company=company_name,
            is_target=True,
            mention_count=target_counts[tier],
            mention_rate=round(target_counts[tier] / total, 4),
        )

        # Top N-1 competitors (excluding target name if it appears in co-mentions)
        competitor_entries = [
            SovEntry(
                company=name,
                is_target=False,
                mention_count=count,
                mention_rate=round(count / total, 4),
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
                total_keywords=total,
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


class KeywordRow(BaseModel):
    keyword: str
    tier: str
    mentioned: bool
    framing: str | None
    recommendation_strength: str | None
    use_case_context: str | None
    counter_positioning: str | None
    exact_quote: str | None


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

    # Fetch all keyword rows for latest run
    try:
        sightings_resp = (
            db.table("brand_geo_sightings")
            .select(
                "keyword, tier, mentioned, framing, recommendation_strength, "
                "use_case_context, counter_positioning, context"
            )
            .eq("company", company)
            .eq("run_at", run["run_at"])
            .order("tier")
            .order("keyword")
            .execute()
        )
    except Exception as exc:
        logger.error("geo_sightings_query_failed", company=company, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query GEO sightings data.",
        )

    sightings: list[dict] = sightings_resp.data or []

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
        )
        for row in sightings
    ]

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
