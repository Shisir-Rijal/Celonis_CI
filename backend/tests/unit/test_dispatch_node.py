"""backend/tests/unit/test_dispatch_node.py

Unit tests for dispatch_node and should_correlate.
Registry and capability functions are mocked.

Issue #63 acceptance criteria:
  - Single task success → one AgentCall, routes to synthesize
  - Two tasks success → two AgentCalls, routes to correlation
  - One task raises twice then succeeds → AgentCall with no error
  - One task raises three times → AgentCall.error set, execution continues
  - Unknown capability → AgentCall.error = "capability not found"
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.orchestration.nodes.dispatch import dispatch_node, should_correlate
from app.orchestration.state import AgentCall


def make_agent_call(capability: str = "test_cap", error: str | None = None) -> AgentCall:
    return AgentCall(
        capability=capability,
        input_params={"company": "Celonis"},
        output={"result": "ok"} if error is None else {},
        sources=[],
        derivation="test",
        persist_to_rag=False,
        started_at=None,
        completed_at=None,
        error=error,
    )


@pytest.fixture
def base_state() -> dict:
    return {
        "query": "test query",
        "session_id": None,
        "decomposed_tasks": [],
        "agent_calls": [],
        "retrieved_context": [],
        "conversation_history": [],
        "validation_results": [],
        "sources": [],
        "derivation": "",
        "final_output": "",
        "retrieval_mode": "standard",
        "discovery_query": None,
    }


# ── Happy paths ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_single_task_success_routes_to_synthesize(base_state) -> None:
    """Single successful task → one AgentCall, should_correlate returns 'synthesize'."""
    mock_fn = AsyncMock(return_value=make_agent_call("wording_analysis"))
    base_state["decomposed_tasks"] = [
        {"capability": "wording_analysis", "params": {"company": "Celonis"}}
    ]

    with patch("app.orchestration.nodes.dispatch.get_capability", return_value=mock_fn):
        result = await dispatch_node(base_state)

    assert len(result["agent_calls"]) == 1
    assert result["agent_calls"][0].error is None

    base_state.update(result)
    assert should_correlate(base_state) == "synthesize"


@pytest.mark.asyncio
async def test_two_tasks_success_routes_to_correlation(base_state) -> None:
    """Two successful tasks → two AgentCalls, should_correlate returns 'correlation'."""
    mock_fn = AsyncMock(side_effect=[
        make_agent_call("wording_analysis"),
        make_agent_call("seo_geo_analysis"),
    ])
    base_state["decomposed_tasks"] = [
        {"capability": "wording_analysis", "params": {"company": "Celonis"}},
        {"capability": "seo_geo_analysis", "params": {"company": "Celonis"}},
    ]

    with patch("app.orchestration.nodes.dispatch.get_capability", return_value=mock_fn):
        result = await dispatch_node(base_state)

    assert len(result["agent_calls"]) == 2
    assert all(c.error is None for c in result["agent_calls"])

    base_state.update(result)
    assert should_correlate(base_state) == "correlation"


@pytest.mark.asyncio
async def test_task_raises_twice_then_succeeds(base_state) -> None:
    """Task fails twice, succeeds on third attempt → AgentCall with no error."""
    mock_fn = AsyncMock(side_effect=[
        RuntimeError("transient error"),
        RuntimeError("transient error"),
        make_agent_call("wording_analysis"),
    ])
    base_state["decomposed_tasks"] = [
        {"capability": "wording_analysis", "params": {}}
    ]

    with (
        patch("app.orchestration.nodes.dispatch.get_capability", return_value=mock_fn),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        result = await dispatch_node(base_state)

    assert len(result["agent_calls"]) == 1
    assert result["agent_calls"][0].error is None


@pytest.mark.asyncio
async def test_task_raises_three_times_sets_error(base_state) -> None:
    """Task fails all 3 attempts → AgentCall.error set, execution continues."""
    mock_fn = AsyncMock(side_effect=RuntimeError("persistent error"))
    base_state["decomposed_tasks"] = [
        {"capability": "wording_analysis", "params": {}}
    ]

    with (
        patch("app.orchestration.nodes.dispatch.get_capability", return_value=mock_fn),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        result = await dispatch_node(base_state)

    assert len(result["agent_calls"]) == 1
    assert result["agent_calls"][0].error == "persistent error"
    assert result["agent_calls"][0].output == {}


@pytest.mark.asyncio
async def test_unknown_capability_sets_error_and_continues(base_state) -> None:
    """Unknown capability → AgentCall.error = 'capability not found', no exception raised."""
    base_state["decomposed_tasks"] = [
        {"capability": "nonexistent_cap", "params": {}}
    ]

    with patch("app.orchestration.nodes.dispatch.get_capability", return_value=None):
        result = await dispatch_node(base_state)

    assert len(result["agent_calls"]) == 1
    assert result["agent_calls"][0].error == "capability not found"
    assert result["agent_calls"][0].capability == "nonexistent_cap"