"""backend/tests/unit/test_assess_node.py

Unit tests for assess_node.
The LLM client is mocked so no OpenAI calls are made.

Issue #61 acceptance criteria:
  - Standard single-capability query → one task, retrieval_mode: "standard"
  - Comparison query → two tasks same capability, retrieval_mode: "standard"
  - Discovery query → retrieval_mode: "agentic", discovery_query set, tasks: []
  - Malformed JSON → AssessmentError
  - Empty task list → valid, retrieval_mode: "standard"
  - agentic + no discovery_query → AssessmentError
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions import AssessmentError
from app.orchestration.nodes.assess import assess_node


@pytest.fixture
def base_state() -> dict:
    return {
        "query": "What is Celonis?",
        "retrieved_context": ["Celonis is a process mining platform."],
        "conversation_history": [],
    }


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.complete = AsyncMock()
    return client


# ── Happy paths ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_standard_single_capability(base_state, mock_client) -> None:
    """Standard query → one task, retrieval_mode 'standard'."""
    mock_client.complete.return_value = json.dumps({
        "tasks": [{"capability": "wording_analysis", "params": {"company": "Celonis"}}],
        "retrieval_mode": "standard",
        "discovery_query": None,
    })

    with patch("app.orchestration.nodes.assess.get_chat_client", return_value=mock_client):
        result = await assess_node(base_state)

    assert result["retrieval_mode"] == "standard"
    assert len(result["decomposed_tasks"]) == 1
    assert result["decomposed_tasks"][0]["capability"] == "wording_analysis"
    assert result["discovery_query"] is None


@pytest.mark.asyncio
async def test_comparison_query_two_tasks(base_state, mock_client) -> None:
    """Comparison query → two tasks with the same capability, one per entity."""
    base_state["query"] = "Compare SAP and Celonis messaging"
    mock_client.complete.return_value = json.dumps({
        "tasks": [
            {"capability": "wording_analysis", "params": {"company": "Celonis"}},
            {"capability": "wording_analysis", "params": {"company": "SAP"}},
        ],
        "retrieval_mode": "standard",
        "discovery_query": None,
    })

    with patch("app.orchestration.nodes.assess.get_chat_client", return_value=mock_client):
        result = await assess_node(base_state)

    assert result["retrieval_mode"] == "standard"
    assert len(result["decomposed_tasks"]) == 2
    capabilities = [t["capability"] for t in result["decomposed_tasks"]]
    assert all(c == "wording_analysis" for c in capabilities)
    companies = {t["params"]["company"] for t in result["decomposed_tasks"]}
    assert companies == {"Celonis", "SAP"}


@pytest.mark.asyncio
async def test_discovery_query_agentic(base_state, mock_client) -> None:
    """Discovery query → retrieval_mode 'agentic', discovery_query set, tasks []."""
    base_state["query"] = "How did analysts react to Celonis Q1?"
    mock_client.complete.return_value = json.dumps({
        "tasks": [],
        "retrieval_mode": "agentic",
        "discovery_query": "Celonis Q1 2026 report",
    })

    with patch("app.orchestration.nodes.assess.get_chat_client", return_value=mock_client):
        result = await assess_node(base_state)

    assert result["retrieval_mode"] == "agentic"
    assert result["discovery_query"] == "Celonis Q1 2026 report"
    assert result["decomposed_tasks"] == []


@pytest.mark.asyncio
async def test_empty_task_list_is_valid(base_state, mock_client) -> None:
    """Empty task list with retrieval_mode 'standard' is valid."""
    mock_client.complete.return_value = json.dumps({
        "tasks": [],
        "retrieval_mode": "standard",
        "discovery_query": None,
    })

    with patch("app.orchestration.nodes.assess.get_chat_client", return_value=mock_client):
        result = await assess_node(base_state)

    assert result["decomposed_tasks"] == []
    assert result["retrieval_mode"] == "standard"


# ── Unhappy paths ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_malformed_json_raises_assessment_error(base_state, mock_client) -> None:
    """Malformed JSON → AssessmentError, not bare JSONDecodeError."""
    mock_client.complete.return_value = "not valid json {{"

    with patch("app.orchestration.nodes.assess.get_chat_client", return_value=mock_client):
        with pytest.raises(AssessmentError):
            await assess_node(base_state)


@pytest.mark.asyncio
async def test_agentic_without_discovery_query_raises(base_state, mock_client) -> None:
    """retrieval_mode 'agentic' with no discovery_query → AssessmentError."""
    mock_client.complete.return_value = json.dumps({
        "tasks": [],
        "retrieval_mode": "agentic",
        "discovery_query": None,
    })

    with patch("app.orchestration.nodes.assess.get_chat_client", return_value=mock_client):
        with pytest.raises(AssessmentError):
            await assess_node(base_state)

@pytest.mark.asyncio
async def test_invalid_tasks_not_a_list_raises(base_state, mock_client) -> None:
    """tasks not a list → AssessmentError."""
    mock_client.complete.return_value = json.dumps({
        "tasks": "not a list",
        "retrieval_mode": "standard",
        "discovery_query": None,
    })

    with patch("app.orchestration.nodes.assess.get_chat_client", return_value=mock_client):
        with pytest.raises(AssessmentError):
            await assess_node(base_state)


@pytest.mark.asyncio
async def test_unknown_retrieval_mode_raises(base_state, mock_client) -> None:
    """Unknown retrieval_mode value → AssessmentError."""
    mock_client.complete.return_value = json.dumps({
        "tasks": [],
        "retrieval_mode": "AGENTIC",
        "discovery_query": None,
    })

    with patch("app.orchestration.nodes.assess.get_chat_client", return_value=mock_client):
        with pytest.raises(AssessmentError):
            await assess_node(base_state)