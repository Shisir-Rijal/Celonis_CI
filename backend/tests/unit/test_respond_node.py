"""backend/tests/unit/test_respond_node.py

Unit tests for respond_node.
save_turn is mocked — no Supabase calls.

Issue #66 acceptance criteria:
  - save_turn called with correct args; returns {}
  - save_turn raising does NOT abort — returns {} and continues
"""

from unittest.mock import patch
from uuid import uuid4

import pytest

from app.models.schemas import Source
from app.orchestration.nodes.respond import respond_node


def make_state(session_id=None) -> dict:
    return {
        "session_id": session_id or uuid4(),
        "query": "What is Celonis?",
        "final_output": "Celonis is a process mining company.",
        "sources": [],
        "derivation": "From retrieved context.",
        "agent_calls": [],
        "decomposed_tasks": [],
        "retrieved_context": [],
        "conversation_history": [],
        "validation_results": [],
        "retrieval_mode": "standard",
        "discovery_query": None,
    }


@pytest.mark.asyncio
async def test_respond_node_calls_save_turn_with_correct_args() -> None:
    """save_turn is called with session_id, query, answer, sources, derivation."""
    session_id = uuid4()
    source = Source(url="https://celonis.com", title="Celonis", relevance_score=0.9)
    state = make_state(session_id)
    state["sources"] = [source]

    with patch("app.orchestration.nodes.respond.save_turn") as mock_save:
        result = await respond_node(state)

    mock_save.assert_called_once_with(
        session_id=session_id,
        query="What is Celonis?",
        answer="Celonis is a process mining company.",
        sources=[source],
        derivation="From retrieved context.",
    )
    assert result == {}


@pytest.mark.asyncio
async def test_respond_node_continues_if_save_turn_raises() -> None:
    """save_turn raising does not abort — respond_node returns {} and continues."""
    with patch(
        "app.orchestration.nodes.respond.save_turn",
        side_effect=Exception("DB error"),
    ):
        result = await respond_node(make_state())

    assert result == {}


@pytest.mark.asyncio
async def test_respond_node_skips_save_turn_if_no_session_id() -> None:
    """respond_node returns {} without calling save_turn when session_id is None."""
    state = make_state()
    state["session_id"] = None

    with patch("app.orchestration.nodes.respond.save_turn") as mock_save:
        result = await respond_node(state)

    mock_save.assert_not_called()
    assert result == {}