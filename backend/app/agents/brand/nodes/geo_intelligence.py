"""backend/app/agents/brand/nodes/geo_intelligence.py

GEO Intelligence capability node for the Brand Intelligence Pipeline.

Execution per configured LLM provider (GPT-4o, Claude Sonnet, Perplexity sonar-pro):
  1. Query each provider for all 30 brand keywords in parallel (Semaphore 5).
  2. Analyse each provider's responses with GPT-4o structured output
     (GeoAnalysisOutput) — same analysis model for all providers so results
     are comparable.
  3. Apply consistency rule: framing=null when recommendation_strength=listed.
  4. Persist all rows to brand_geo_sightings (llm column identifies provider).
  5. Run synthesis with o4-mini over all sightings → GeoSynthesisOutput.
  6. Return CapabilityResult.

Active providers are determined by API keys in settings. OpenAI is always
active. Claude and Perplexity are opt-in (see geo_providers.py).
"""

import asyncio
import structlog
from datetime import datetime, timezone
from typing import Any

from langchain_core.language_models import BaseChatModel

from app.agents.brand.capability import CapabilityResult
from app.agents.brand.geo_providers import (
    GeoQueryProvider,
    build_analysis_llm,
    build_query_providers,
    build_synthesis_llm,
)
from app.agents.brand.keywords import ALL_BRAND_KEYWORDS, KEYWORD_TIER
from app.agents.brand.repositories.geo_repository import (
    GeoSightingRow,
    insert_geo_run,
    insert_geo_sightings,
)
from app.agents.brand.state import BrandPipelineState
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


async def _query_geo_keyword(
    keyword: str,
    llm: BaseChatModel,
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
        # Build shared analysis LLM once (used for all providers)
        # ------------------------------------------------------------------
        structured_analysis_llm = build_analysis_llm().with_structured_output(
            GeoAnalysisOutput,
            method="json_schema",
            strict=True,
        )

        providers: list[GeoQueryProvider] = build_query_providers()
        logger.info(
            "geo_providers_active",
            company=company,
            providers=[p.name for p in providers],
        )

        all_rows: list[GeoSightingRow] = []
        # analyses from the last provider — used for synthesis input
        last_analyses: dict[str, GeoAnalysisOutput | None] = {}

        for provider in providers:
            # --------------------------------------------------------------
            # Phase 1 — GEO queries: ask this provider what companies lead
            # each keyword
            # --------------------------------------------------------------
            raw_responses: dict[str, str] = {}
            query_tasks = {
                kw: _query_geo_keyword(kw, provider.llm)
                for kw in ALL_BRAND_KEYWORDS
            }
            query_results = await asyncio.gather(
                *query_tasks.values(), return_exceptions=True
            )
            for keyword, result in zip(query_tasks.keys(), query_results):
                if isinstance(result, Exception):
                    logger.warning(
                        "geo_query_failed",
                        provider=provider.name,
                        keyword=keyword,
                        error=str(result),
                    )
                    raw_responses[keyword] = ""
                else:
                    raw_responses[keyword] = result

            logger.info(
                "geo_queries_done",
                company=company,
                provider=provider.name,
                total=len(ALL_BRAND_KEYWORDS),
            )

            # --------------------------------------------------------------
            # Phase 2 — Structured analysis (always GPT-4o for consistency)
            # --------------------------------------------------------------
            analyses: dict[str, GeoAnalysisOutput | None] = {}
            analysis_tasks = {
                kw: _analyse_keyword(kw, raw_responses[kw], company_name, structured_analysis_llm)
                for kw in ALL_BRAND_KEYWORDS
                if raw_responses.get(kw)
            }
            analysis_results = await asyncio.gather(
                *analysis_tasks.values(), return_exceptions=True
            )
            for keyword, result in zip(analysis_tasks.keys(), analysis_results):
                if isinstance(result, Exception):
                    logger.warning(
                        "geo_analysis_failed",
                        provider=provider.name,
                        keyword=keyword,
                        error=str(result),
                    )
                    analyses[keyword] = None
                else:
                    analyses[keyword] = _apply_consistency_rules(result)

            logger.info(
                "geo_analyses_done",
                company=company,
                provider=provider.name,
                successful=sum(1 for v in analyses.values() if v is not None),
            )

            # Collect rows for this provider
            for keyword in ALL_BRAND_KEYWORDS:
                analysis = analyses.get(keyword)
                if analysis is not None:
                    all_rows.append(
                        _build_sighting_row(keyword, analysis, company, run_at, provider.name)
                    )

            last_analyses = analyses

        # ------------------------------------------------------------------
        # Phase 3 — Persist all rows from all providers (bulk insert)
        # ------------------------------------------------------------------
        try:
            insert_geo_sightings(all_rows)
            logger.info("geo_sightings_persisted", company=company, rows=len(all_rows))
        except Exception as exc:
            logger.error("geo_persist_failed", company=company, error=str(exc))
            # Non-fatal: continue to synthesis

        # ------------------------------------------------------------------
        # Phase 3.5 — Compute recommendation_rate (averaged across providers)
        # ------------------------------------------------------------------
        total_keywords_across_providers = len(ALL_BRAND_KEYWORDS) * len(providers)
        rec_count = sum(
            1 for row in all_rows
            if row.recommendation_strength in ("recommended", "organic")
        )
        recommendation_rate = rec_count / total_keywords_across_providers if total_keywords_across_providers else 0.0

        # ------------------------------------------------------------------
        # Phase 4 — Synthesis (o4-mini over aggregated sightings)
        # Uses last_analyses as representative input — synthesis is
        # cross-provider and strategic, not per-provider.
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
            for kw, a in last_analyses.items()
            if a is not None
        ]

        synthesis: GeoSynthesisOutput | None = None
        try:
            structured_synthesis_llm = build_synthesis_llm().with_structured_output(
                GeoSynthesisOutput,
                method="json_schema",
                strict=True,
            )
            messages = build_geo_synthesis_messages(
                sightings_for_synthesis, company_name, len(ALL_BRAND_KEYWORDS)
            )
            synthesis = await structured_synthesis_llm.ainvoke(messages)
            logger.info("geo_synthesis_done", company=company)

            try:
                insert_geo_run(company, run_at, synthesis, recommendation_rate)
                logger.info("geo_run_persisted", company=company)
            except Exception as persist_exc:
                logger.error("geo_run_persist_failed", company=company, error=str(persist_exc))
        except Exception as exc:
            logger.error("geo_synthesis_failed", company=company, error=str(exc))

        # ------------------------------------------------------------------
        # Phase 5 — Return CapabilityResult
        # mention_rate averaged across all providers and keywords
        # ------------------------------------------------------------------
        total_possible = len(ALL_BRAND_KEYWORDS) * len(providers)
        mention_count = sum(1 for row in all_rows if row.mentioned)
        mention_rate = mention_count / total_possible if total_possible else 0.0
        gap_keywords = [
            kw for kw, a in last_analyses.items()
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
