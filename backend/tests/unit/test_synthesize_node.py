"""backend/tests/unit/test_synthesize_node.py

Unit tests for synthesize_node.
LLM client is mocked.

Issue #64 acceptance criteria:
  - 0 successful calls → answer from retrieved_context, sources = []
  - 1 successful call → AgentCall.sources appear in final sources
  - 2 successful calls → both outputs in prompt, sources merged and deduplicated
  - LLM raises → exception propagates
  - retrieved_context empty + no successful calls → hardcoded answer, no LLM call
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.schemas import Source
from app.orchestration.nodes.synthesize import synthesize_node
from app.orchestration.state import AgentCall


def make_source(url: str, title: str = "Test") -> Source:
    return Source(url=url, title=title, relevance_score=0.9)


def make_agent_call(
    capability: str = "test_cap",
    error: str | None = None,
    sources: list[Source] | None = None,
) -> AgentCall:
    return AgentCall(
        capability=capability,
        input_params={},
        output={"result": "test output"} if error is None else {},
        sources=sources or [],
        derivation="test derivation",
        persist_to_rag=False,
        started_at=None,
        completed_at=None,
        error=error,
    )


@pytest.fixture
def base_state() -> dict:
    return {
        "query": "What is Celonis?",
        "session_id": None,
        "agent_calls": [],
        "retrieved_context": [],
        "conversation_history": [],
        "decomposed_tasks": [],
        "validation_results": [],
        "sources": [],
        "derivation": "",
        "final_output": "",
        "retrieval_mode": "standard",
        "discovery_query": None,
    }


@pytest.fixture
def mock_llm_client():
    client = MagicMock()
    client.complete = AsyncMock()
    return client


# ── Happy paths ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_zero_successful_calls_uses_retrieved_context(
    base_state, mock_llm_client
) -> None:
    """0 successful calls → LLM uses retrieved_context, sources = []."""
    base_state["agent_calls"] = [make_agent_call(error="failed")]
    base_state["retrieved_context"] = ["Celonis is a process mining platform."]
    mock_llm_client.complete.return_value = json.dumps({
        "answer": "Celonis does process mining.",
        "derivation": "From retrieved context.",
    })

    with patch(
        "app.orchestration.nodes.synthesize.get_chat_client",
        return_value=mock_llm_client,
    ):
        result = await synthesize_node(base_state)

    assert result["final_output"] == "Celonis does process mining."
    assert result["sources"] == []
    assert result["derivation"] == "From retrieved context."


@pytest.mark.asyncio
async def test_one_successful_call_sources_in_result(
    base_state, mock_llm_client
) -> None:
    """1 successful call → AgentCall.sources appear in final sources."""
    source = make_source("https://celonis.com", "Celonis homepage")
    base_state["agent_calls"] = [make_agent_call(sources=[source])]
    mock_llm_client.complete.return_value = json.dumps({
        "answer": "Celonis is a leader in process mining.",
        "derivation": "Based on wording_analysis output.",
    })

    with patch(
        "app.orchestration.nodes.synthesize.get_chat_client",
        return_value=mock_llm_client,
    ):
        result = await synthesize_node(base_state)

    assert result["final_output"] == "Celonis is a leader in process mining."
    assert len(result["sources"]) == 1
    assert result["sources"][0].url == "https://celonis.com"


@pytest.mark.asyncio
async def test_two_successful_calls_sources_merged_and_deduplicated(
    base_state, mock_llm_client
) -> None:
    """2 successful calls → sources merged; duplicate URLs deduplicated."""
    shared_url = "https://celonis.com/shared"
    source_a = make_source(shared_url, "Shared source A")
    source_b = make_source(shared_url, "Shared source B")  # same URL → deduped
    source_c = make_source("https://celonis.com/unique", "Unique source")

    base_state["agent_calls"] = [
        make_agent_call(capability="cap_a", sources=[source_a, source_c]),
        make_agent_call(capability="cap_b", sources=[source_b]),
    ]
    mock_llm_client.complete.return_value = json.dumps({
        "answer": "Combined narrative answer.",
        "derivation": "Synthesised from cap_a and cap_b.",
    })

    with patch(
        "app.orchestration.nodes.synthesize.get_chat_client",
        return_value=mock_llm_client,
    ):
        result = await synthesize_node(base_state)

    assert result["final_output"] == "Combined narrative answer."
    urls = {s.url for s in result["sources"]}
    assert urls == {shared_url, "https://celonis.com/unique"}  # deduplicated


# ── Unhappy paths ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_llm_raises_exception_propagates(
    base_state, mock_llm_client
) -> None:
    """LLM exception propagates out of synthesize_node."""
    base_state["retrieved_context"] = ["Some context."]
    mock_llm_client.complete.side_effect = RuntimeError("LLM provider error")

    with patch(
        "app.orchestration.nodes.synthesize.get_chat_client",
        return_value=mock_llm_client,
    ):
        with pytest.raises(RuntimeError, match="LLM provider error"):
            await synthesize_node(base_state)


@pytest.mark.asyncio
async def test_empty_context_and_no_successful_calls_no_llm(
    base_state, mock_llm_client
) -> None:
    """No retrieved_context + no successful calls → hardcoded answer, no LLM call."""
    base_state["agent_calls"] = [make_agent_call(error="failed")]
    base_state["retrieved_context"] = []

    with patch(
        "app.orchestration.nodes.synthesize.get_chat_client",
        return_value=mock_llm_client,
    ):
        result = await synthesize_node(base_state)

    assert result["final_output"] == "No relevant information found."
    assert result["sources"] == []
    assert result["derivation"] == ""
    mock_llm_client.complete.assert_not_called()