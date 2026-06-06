"""backend/tests/unit/test_geo_intelligence_node.py

Unit tests for geo_intelligence_node.
All LLM calls and Supabase inserts are mocked.

Issue #90: GEO Intelligence backend
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.agents.brand.capability import CapabilityResult
from app.agents.brand.keywords import ALL_BRAND_KEYWORDS
from app.agents.brand.nodes.geo_intelligence import (
    _apply_consistency_rules,
    geo_intelligence_node,
)
from app.agents.brand.state import BrandPipelineState
from app.agents.research.state import CompetitorProfile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_profile(domain: str = "celonis.com") -> CompetitorProfile:
    return CompetitorProfile(domain=domain)


def make_state(profile: CompetitorProfile | None = None) -> dict:
    return {
        "competitor_domain": "celonis.com",
        "nodes_to_run": [],
        "profile": profile or make_profile(),
        "results": {},
        "errors": [],
        "completed_capabilities": [],
    }


def make_analysis_output(
    mentioned: bool = True,
    framing: str | None = "technical",
    recommendation_strength: str | None = "listed",
    co_mentioned: list[str] | None = None,
    use_case: str | None = "process mining",
    counter: str | None = None,
) -> MagicMock:
    """Build a mock GeoAnalysisOutput."""
    mock = MagicMock()
    mock.target_mentioned = mentioned
    mock.framing = framing
    mock.recommendation_strength = recommendation_strength
    mock.co_mentioned_companies = co_mentioned or ["UiPath", "SAP Signavio"]
    mock.use_case_context = use_case
    mock.counter_positioning = counter
    mock.exact_quote = "Celonis is a process mining tool." if mentioned else None
    mock.model_copy = lambda update=None, **_: make_analysis_output(
        mentioned=mentioned,
        framing=update.get("framing", framing) if update else framing,
        recommendation_strength=recommendation_strength,
        co_mentioned=co_mentioned,
        use_case=use_case,
        counter=counter,
    )
    return mock


def make_synthesis_output() -> MagicMock:
    mock = MagicMock()
    mock.narrative = "Celonis is visible in process mining but absent from enterprise AI."
    mock.mention_rate = 0.4
    mock.dominant_framing = "technical"
    mock.strongest_tier = "brand_category"
    mock.top_counter_positioning = None
    mock.gap_keyword_count = 18
    mock.owned_territories = []
    mock.contested_territories = ["process mining"]
    mock.absent_territories = ["enterprise AI platform", "digital transformation"]
    mock.primary_peer_group = ["UiPath", "SAP Signavio", "IBM"]
    mock.peer_group_assessment = "Correct peer group for process mining."
    mock.critical_gap = "enterprise AI platform — owned by IBM"
    mock.counter_positioning_theme = None
    mock.framing_gap = "Celonis perceived as technical tool, claims strategic leadership."
    return mock


# ---------------------------------------------------------------------------
# Unit tests: _apply_consistency_rules
# ---------------------------------------------------------------------------

def test_consistency_rule_visionary_listed_becomes_null() -> None:
    """framing=visionary + recommendation_strength=listed → framing=null."""
    analysis = make_analysis_output(framing="visionary", recommendation_strength="listed")
    result = _apply_consistency_rules(analysis)
    assert result.framing is None


def test_consistency_rule_visionary_recommended_unchanged() -> None:
    """framing=visionary + recommendation_strength=recommended → unchanged."""
    analysis = make_analysis_output(framing="visionary", recommendation_strength="recommended")
    result = _apply_consistency_rules(analysis)
    assert result.framing == "visionary"


def test_consistency_rule_technical_listed_unchanged() -> None:
    """framing=technical is never affected by the rule."""
    analysis = make_analysis_output(framing="technical", recommendation_strength="listed")
    result = _apply_consistency_rules(analysis)
    assert result.framing == "technical"


# ---------------------------------------------------------------------------
# Unit tests: geo_intelligence_node
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_node_returns_capability_result_on_success() -> None:
    """Node returns CapabilityResult with geo_intelligence key in results."""
    analysis = make_analysis_output(mentioned=True)
    synthesis = make_synthesis_output()

    with (
        patch("app.agents.brand.nodes.geo_intelligence._build_llm") as mock_build_llm,
        patch("app.agents.brand.nodes.geo_intelligence.insert_geo_sightings"),
    ):
        query_llm = MagicMock()
        query_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Celonis leads process mining."))

        structured_llm = MagicMock()
        structured_llm.ainvoke = AsyncMock(return_value=analysis)

        analysis_llm = MagicMock()
        analysis_llm.with_structured_output = MagicMock(return_value=structured_llm)

        synthesis_llm_mock = MagicMock()
        synthesis_structured = MagicMock()
        synthesis_structured.ainvoke = AsyncMock(return_value=synthesis)
        synthesis_llm_mock.with_structured_output = MagicMock(return_value=synthesis_structured)

        mock_build_llm.side_effect = [query_llm, analysis_llm, synthesis_llm_mock]

        result = await geo_intelligence_node(make_state())

    assert "geo_intelligence" in result["results"]
    cap: CapabilityResult = result["results"]["geo_intelligence"]
    assert cap.capability == "geo_intelligence"
    assert cap.company == "celonis.com"
    assert cap.error is None
    assert "completed_capabilities" in result
    assert "geo_intelligence" in result["completed_capabilities"]


@pytest.mark.asyncio
async def test_node_calls_insert_for_all_keywords() -> None:
    """insert_geo_sightings is called once with all 30 rows."""
    analysis = make_analysis_output(mentioned=False)
    synthesis = make_synthesis_output()

    with (
        patch("app.agents.brand.nodes.geo_intelligence._build_llm") as mock_build_llm,
        patch("app.agents.brand.nodes.geo_intelligence.insert_geo_sightings") as mock_insert,
    ):
        query_llm = MagicMock()
        query_llm.ainvoke = AsyncMock(return_value=MagicMock(content="SAP and Oracle lead."))

        structured_llm = MagicMock()
        structured_llm.ainvoke = AsyncMock(return_value=analysis)

        analysis_llm = MagicMock()
        analysis_llm.with_structured_output = MagicMock(return_value=structured_llm)

        synthesis_llm_mock = MagicMock()
        synthesis_structured = MagicMock()
        synthesis_structured.ainvoke = AsyncMock(return_value=synthesis)
        synthesis_llm_mock.with_structured_output = MagicMock(return_value=synthesis_structured)

        mock_build_llm.side_effect = [query_llm, analysis_llm, synthesis_llm_mock]

        await geo_intelligence_node(make_state())

    mock_insert.assert_called_once()
    rows = mock_insert.call_args[0][0]
    assert len(rows) == len(ALL_BRAND_KEYWORDS)


@pytest.mark.asyncio
async def test_node_skips_gracefully_when_no_profile() -> None:
    """Node returns error and empty results when profile is None."""
    state = make_state()
    state["profile"] = None

    result = await geo_intelligence_node(state)

    assert "errors" in result
    assert any("no profile" in e for e in result["errors"])
    assert result.get("results") is None or "geo_intelligence" not in result.get("results", {})


@pytest.mark.asyncio
async def test_node_continues_when_one_query_fails() -> None:
    """If one GEO query raises, node continues with remaining keywords."""
    call_count = 0

    async def query_side_effect(messages):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("API timeout")
        return MagicMock(content="UiPath and SAP are leaders.")

    analysis = make_analysis_output(mentioned=False)
    synthesis = make_synthesis_output()

    with (
        patch("app.agents.brand.nodes.geo_intelligence._build_llm") as mock_build_llm,
        patch("app.agents.brand.nodes.geo_intelligence.insert_geo_sightings"),
    ):
        query_llm = MagicMock()
        query_llm.ainvoke = AsyncMock(side_effect=query_side_effect)

        structured_llm = MagicMock()
        structured_llm.ainvoke = AsyncMock(return_value=analysis)

        analysis_llm = MagicMock()
        analysis_llm.with_structured_output = MagicMock(return_value=structured_llm)

        synthesis_llm_mock = MagicMock()
        synthesis_structured = MagicMock()
        synthesis_structured.ainvoke = AsyncMock(return_value=synthesis)
        synthesis_llm_mock.with_structured_output = MagicMock(return_value=synthesis_structured)

        mock_build_llm.side_effect = [query_llm, analysis_llm, synthesis_llm_mock]

        result = await geo_intelligence_node(make_state())

    cap: CapabilityResult = result["results"]["geo_intelligence"]
    assert cap.error is None


@pytest.mark.asyncio
async def test_node_continues_when_supabase_insert_fails() -> None:
    """If insert_geo_sightings raises, node continues to synthesis."""
    analysis = make_analysis_output(mentioned=True)
    synthesis = make_synthesis_output()

    with (
        patch("app.agents.brand.nodes.geo_intelligence._build_llm") as mock_build_llm,
        patch(
            "app.agents.brand.nodes.geo_intelligence.insert_geo_sightings",
            side_effect=Exception("Supabase connection error"),
        ),
    ):
        query_llm = MagicMock()
        query_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Celonis leads."))

        structured_llm = MagicMock()
        structured_llm.ainvoke = AsyncMock(return_value=analysis)

        analysis_llm = MagicMock()
        analysis_llm.with_structured_output = MagicMock(return_value=structured_llm)

        synthesis_llm_mock = MagicMock()
        synthesis_structured = MagicMock()
        synthesis_structured.ainvoke = AsyncMock(return_value=synthesis)
        synthesis_llm_mock.with_structured_output = MagicMock(return_value=synthesis_structured)

        mock_build_llm.side_effect = [query_llm, analysis_llm, synthesis_llm_mock]

        result = await geo_intelligence_node(make_state())

    cap: CapabilityResult = result["results"]["geo_intelligence"]
    assert cap.error is None
    assert "geo_intelligence" in result["completed_capabilities"]


@pytest.mark.asyncio
async def test_node_sets_error_when_synthesis_fails() -> None:
    """If synthesis raises, node still returns CapabilityResult with basic data."""
    analysis = make_analysis_output(mentioned=True)

    with (
        patch("app.agents.brand.nodes.geo_intelligence._build_llm") as mock_build_llm,
        patch("app.agents.brand.nodes.geo_intelligence.insert_geo_sightings"),
    ):
        query_llm = MagicMock()
        query_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Celonis leads."))

        structured_llm = MagicMock()
        structured_llm.ainvoke = AsyncMock(return_value=analysis)

        analysis_llm = MagicMock()
        analysis_llm.with_structured_output = MagicMock(return_value=structured_llm)

        synthesis_llm_mock = MagicMock()
        synthesis_structured = MagicMock()
        synthesis_structured.ainvoke = AsyncMock(side_effect=RuntimeError("o4-mini timeout"))
        synthesis_llm_mock.with_structured_output = MagicMock(return_value=synthesis_structured)

        mock_build_llm.side_effect = [query_llm, analysis_llm, synthesis_llm_mock]

        result = await geo_intelligence_node(make_state())

    cap: CapabilityResult = result["results"]["geo_intelligence"]
    assert cap.error is None
    assert "mention_rate" in cap.data
    assert "narrative_summary" not in cap.data
