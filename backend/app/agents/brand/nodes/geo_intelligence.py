"""backend/app/agents/brand/nodes/geo_intelligence.py

GEO Intelligence capability node for the Brand Intelligence Pipeline.

Execution:
  1. Query GPT-4o-mini for all 30 brand keywords in parallel (Semaphore 5).
  2. Run structured analysis (GeoAnalysisOutput) for all keywords in parallel.
     Non-mentions get co_mentioned_companies + use_case_context; classification
     fields are null by schema design.
  3. Apply post-processing consistency rule: framing=null when
     recommendation_strength=listed (prevents list-preamble misclassification).
  4. Persist all rows to brand_geo_sightings via bulk insert.
  5. Run synthesis call (o4-mini) over all results → GeoSynthesisOutput.
  6. Return CapabilityResult.

Issue #90: GEO Intelligence backend
"""

import asyncio
import json
import structlog
from datetime import datetime, timezone
from typing import Any

from langchain_openai import ChatOpenAI

from app.agents.brand.capability import CapabilityResult
from app.agents.brand.keywords import ALL_BRAND_KEYWORDS, KEYWORD_TIER
from app.agents.brand.repositories.geo_repository import (
    GeoSightingRow,
    insert_geo_sightings,
)
from app.agents.brand.state import BrandPipelineState
from app.config import get_settings
from app.prompts.brand.geo_analysis import (
    GeoAnalysisOutput,
    build_geo_analysis_messages,
)
from app.prompts.brand.geo_synthesis import (
    GeoSynthesisOutput,
    build_geo_synthesis_messages,
)

logger = structlog.get_logger(__name__)

_GEO_QUERY_SEMAPHORE = asyncio.Semaphore(5)
_ANALYSIS_SEMAPHORE = asyncio.Semaphore(5)
_LLM_MODEL = "gpt-4o-mini"
_SYNTHESIS_MODEL = "o4-mini"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_llm(model: str, temperature: float = 0.0) -> ChatOpenAI:
    """Build a ChatOpenAI instance from project settings."""
    settings = get_settings()
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL or "https://api.openai.com/v1",
    )


async def _query_geo_keyword(
    keyword: str,
    llm: ChatOpenAI,
) -> str:
    """Ask GPT what companies are known for this keyword.

    Returns the raw LLM response string.
    """
    async with _GEO_QUERY_SEMAPHORE:
        response = await llm.ainvoke([
            {
                "role": "system",
                "content": (
                    "Answer concisely. List the main companies or products "
                    "known for this topic."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Which companies or platforms are the leading providers "
                    f"for: {keyword}?"
                ),
            },
        ])
        return response.content


async def _analyse_keyword(
    keyword: str,
    raw_response: str,
    company: str,
    structured_llm: Any,
) -> GeoAnalysisOutput:
    """Run structured brand analysis on one keyword's GEO response."""
    async with _ANALYSIS_SEMAPHORE:
        messages = build_geo_analysis_messages(keyword, raw_response, company)
        result: GeoAnalysisOutput = await structured_llm.ainvoke(messages)
        return result


def _apply_consistency_rules(result: GeoAnalysisOutput) -> GeoAnalysisOutput:
    """Post-processing: fix logical contradictions in classification fields.

    Rule: framing cannot be 'visionary' when recommendation_strength is
    'listed'. Being enumerated in a list with no specific descriptor is
    incompatible with visionary framing. This catches the list-preamble
    misclassification ('The leading providers include: X, Y, Z').
    """
    if result.framing == "visionary" and result.recommendation_strength == "listed":
        return result.model_copy(update={"framing": None})
    return result


def _build_sighting_row(
    keyword: str,
    analysis: GeoAnalysisOutput,
    company: str,
    run_at: datetime,
    llm: str,
) -> GeoSightingRow:
    """Map GeoAnalysisOutput to a GeoSightingRow for persistence."""
    return GeoSightingRow(
        company=company,
        run_at=run_at,
        keyword=keyword,
        tier=KEYWORD_TIER.get(keyword, "unknown"),
        llm=llm,
        mentioned=analysis.target_mentioned,
        context=analysis.exact_quote,
        raw_response=None,  # not persisted to save space
        co_mentioned_companies=analysis.co_mentioned_companies or [],
        framing=analysis.framing,
        recommendation_strength=analysis.recommendation_strength,
        use_case_context=analysis.use_case_context,
        counter_positioning=analysis.counter_positioning,
    )


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

async def geo_intelligence_node(state: BrandPipelineState) -> dict:
    """GEO Intelligence capability node.

    Reads state["profile"] for company domain. Runs the full keyword
    pipeline and returns a CapabilityResult.

    Returns {} if profile is missing (guard — no crash).
    Returns CapabilityResult with error set if any phase fails critically.
    """
    profile = state.get("profile")
    if profile is None:
        logger.warning("geo_intelligence_skipped", reason="no_profile")
        return {
            "errors": ["geo_intelligence: no profile available"],
        }

    company = profile.domain
    # Extract just the company name for LLM matching (e.g. "celonis" from "celonis.com")
    company_name = company.split(".")[0].capitalize()
    run_at = datetime.now(timezone.utc)

    logger.info("geo_intelligence_started", company=company, keywords=len(ALL_BRAND_KEYWORDS))

    try:
        # ------------------------------------------------------------------
        # Phase 1 — GEO queries: ask GPT what companies lead each keyword
        # ------------------------------------------------------------------
        query_llm = _build_llm(_LLM_MODEL, temperature=0.0)

        raw_responses: dict[str, str] = {}
        query_tasks = {
            kw: _query_geo_keyword(kw, query_llm)
            for kw in ALL_BRAND_KEYWORDS
        }
        query_results = await asyncio.gather(
            *query_tasks.values(), return_exceptions=True
        )
        for keyword, result in zip(query_tasks.keys(), query_results):
            if isinstance(result, Exception):
                logger.warning("geo_query_failed", keyword=keyword, error=str(result))
                raw_responses[keyword] = ""
            else:
                raw_responses[keyword] = result

        logger.info("geo_queries_done", company=company, total=len(ALL_BRAND_KEYWORDS))

        # ------------------------------------------------------------------
        # Phase 2 — Structured analysis for all keywords
        # ------------------------------------------------------------------
        analysis_llm = _build_llm(_LLM_MODEL, temperature=0.0)
        structured_llm = analysis_llm.with_structured_output(
            GeoAnalysisOutput,
            method="json_schema",
            strict=True,
        )

        analyses: dict[str, GeoAnalysisOutput | None] = {}
        analysis_tasks = {
            kw: _analyse_keyword(kw, raw_responses[kw], company_name, structured_llm)
            for kw in ALL_BRAND_KEYWORDS
            if raw_responses.get(kw)
        }
        analysis_results = await asyncio.gather(
            *analysis_tasks.values(), return_exceptions=True
        )
        for keyword, result in zip(analysis_tasks.keys(), analysis_results):
            if isinstance(result, Exception):
                logger.warning("geo_analysis_failed", keyword=keyword, error=str(result))
                analyses[keyword] = None
            else:
                analyses[keyword] = _apply_consistency_rules(result)

        logger.info(
            "geo_analyses_done",
            company=company,
            successful=sum(1 for v in analyses.values() if v is not None),
        )

        # ------------------------------------------------------------------
        # Phase 3 — Persist all rows (bulk insert)
        # ------------------------------------------------------------------
        rows = []
        for keyword in ALL_BRAND_KEYWORDS:
            analysis = analyses.get(keyword)
            if analysis is None:
                continue
            rows.append(_build_sighting_row(keyword, analysis, company, run_at, _LLM_MODEL))

        try:
            insert_geo_sightings(rows)
            logger.info("geo_sightings_persisted", company=company, rows=len(rows))
        except Exception as exc:
            logger.error("geo_persist_failed", company=company, error=str(exc))
            # Non-fatal: continue to synthesis

        # ------------------------------------------------------------------
        # Phase 4 — Synthesis (o4-mini over all results)
        # ------------------------------------------------------------------
        sightings_for_synthesis = [
            {
                "keyword": kw,
                "tier": KEYWORD_TIER.get(kw, "unknown"),
                "mentioned": a.target_mentioned,
                "co_mentioned_companies": a.co_mentioned_companies,
                "framing": a.framing,
                "recommendation_strength": a.recommendation_strength,
                "use_case_context": a.use_case_context,
                "counter_positioning": a.counter_positioning,
            }
            for kw, a in analyses.items()
            if a is not None
        ]

        synthesis: GeoSynthesisOutput | None = None
        try:
            # o4-mini is a reasoning model — only supports default temperature (1)
            synthesis_llm = _build_llm(_SYNTHESIS_MODEL, temperature=1.0)
            structured_synthesis_llm = synthesis_llm.with_structured_output(
                GeoSynthesisOutput,
                method="json_schema",
                strict=True,
            )
            messages = build_geo_synthesis_messages(
                sightings_for_synthesis, company_name, len(ALL_BRAND_KEYWORDS)
            )
            synthesis = await structured_synthesis_llm.ainvoke(messages)
            logger.info("geo_synthesis_done", company=company)
        except Exception as exc:
            logger.error("geo_synthesis_failed", company=company, error=str(exc))

        # ------------------------------------------------------------------
        # Phase 5 — Return CapabilityResult
        # ------------------------------------------------------------------
        mentions = [a for a in analyses.values() if a is not None and a.target_mentioned]
        mention_rate = len(mentions) / len(ALL_BRAND_KEYWORDS) if ALL_BRAND_KEYWORDS else 0.0
        gap_keywords = [
            kw for kw, a in analyses.items()
            if a is not None and not a.target_mentioned
        ]

        data: dict[str, Any] = {
            "mention_rate": mention_rate,
            "gap_keywords": gap_keywords,
            "gap_keyword_count": len(gap_keywords),
        }

        if synthesis:
            data.update({
                "narrative_summary": synthesis.narrative,
                "critical_gap": synthesis.critical_gap,
                "owned_territories": synthesis.owned_territories,
                "contested_territories": synthesis.contested_territories,
                "absent_territories": synthesis.absent_territories,
                "primary_peer_group": synthesis.primary_peer_group,
                "peer_group_assessment": synthesis.peer_group_assessment,
                "counter_positioning_theme": synthesis.counter_positioning_theme,
                "framing_gap": synthesis.framing_gap,
                "dominant_framing": synthesis.dominant_framing,
                "strongest_tier": synthesis.strongest_tier,
                "top_counter_positioning": synthesis.top_counter_positioning,
            })

        logger.info(
            "geo_intelligence_done",
            company=company,
            mention_rate=round(mention_rate, 2),
            gap_count=len(gap_keywords),
        )

        return {
            "results": {
                **state.get("results", {}),
                "geo_intelligence": CapabilityResult(
                    capability="geo_intelligence",
                    company=company,
                    run_at=run_at,
                    data=data,
                ),
            },
            "completed_capabilities": ["geo_intelligence"],
        }

    except Exception as exc:
        logger.error("geo_intelligence_failed", company=company, error=str(exc))
        return {
            "results": {
                **state.get("results", {}),
                "geo_intelligence": CapabilityResult(
                    capability="geo_intelligence",
                    company=company,
                    run_at=run_at,
                    data={},
                    error=str(exc),
                ),
            },
            "errors": [f"geo_intelligence: {exc}"],
        }
