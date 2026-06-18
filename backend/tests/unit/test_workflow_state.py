"""backend/tests/unit/test_workflow_state.py

Unit tests for WorkflowState, AgentCall, and ConversationTurn.

Covers all acceptance criteria from Issue #57:
  - AgentCall serialises/deserialises via Pydantic (round-trip)
  - AgentCall with error set and partial output is valid
  - ConversationTurn with both roles is valid
  - WorkflowState can be constructed with all new fields
  - AgentCall without optional fields defaults correctly
  - ConversationTurn with invalid role raises ValidationError
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.schemas import Source
from app.orchestration.state import AgentCall, ConversationTurn, WorkflowState


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def source() -> Source:
    return Source(url="https://celonis.com", title="Celonis homepage", relevance_score=0.9)


@pytest.fixture
def now() -> datetime:
    return datetime.now(tz=timezone.utc)


@pytest.fixture
def minimal_agent_call(source: Source) -> AgentCall:
    return AgentCall(
        capability="web_search",
        input_params={"query": "celonis competitors"},
        output={"results": ["SAP", "IBM"]},
        sources=[source],
        derivation="Retrieved via SerpAPI",
    )


# ── AgentCall ─────────────────────────────────────────────────────────────────

def test_agent_call_round_trip(minimal_agent_call: AgentCall) -> None:
    """AgentCall serialises and deserialises without data loss."""
    data = minimal_agent_call.model_dump(mode="json")
    restored = AgentCall.model_validate(data)
    assert restored == minimal_agent_call


def test_agent_call_optional_fields_default_to_none(minimal_agent_call: AgentCall) -> None:
    """started_at, completed_at, and error must default to None."""
    assert minimal_agent_call.started_at is None
    assert minimal_agent_call.completed_at is None
    assert minimal_agent_call.error is None


def test_agent_call_persist_to_rag_defaults_false(minimal_agent_call: AgentCall) -> None:
    assert minimal_agent_call.persist_to_rag is False


def test_agent_call_with_error_and_partial_output_is_valid(source: Source) -> None:
    """An AgentCall with error set and empty output dict is still valid."""
    call = AgentCall(
        capability="financials",
        input_params={"company": "Celonis"},
        output={},              # partial — Critic enforces completeness at runtime
        sources=[],
        derivation="",
        error="API timeout after 30s",
    )
    assert call.error == "API timeout after 30s"
    assert call.output == {}


def test_agent_call_persist_to_rag_true_with_empty_sources_is_valid(source: Source) -> None:
    """persist_to_rag=True with empty sources is valid (Critic enforces at runtime)."""
    call = AgentCall(
        capability="seo",
        input_params={},
        output={"score": 62},
        sources=[],             # Critic will flag this at runtime, not schema
        derivation="SEO score",
        persist_to_rag=True,
    )
    assert call.persist_to_rag is True


# ── ConversationTurn ──────────────────────────────────────────────────────────

def test_conversation_turn_user_role(now: datetime) -> None:
    turn = ConversationTurn(role="user", content="What is Celonis?", created_at=now)
    assert turn.role == "user"
    assert turn.sources == []
    assert turn.derivation == ""


def test_conversation_turn_assistant_role(source: Source, now: datetime) -> None:
    turn = ConversationTurn(
        role="assistant",
        content="Celonis is a process mining platform.",
        sources=[source],
        derivation="Synthesised from RAG context",
        created_at=now,
    )
    assert turn.role == "assistant"
    assert len(turn.sources) == 1


def test_conversation_turn_invalid_role_raises_validation_error(now: datetime) -> None:
    """A role outside ['user', 'assistant'] must raise Pydantic ValidationError."""
    with pytest.raises(ValidationError):
        ConversationTurn(
            role="system",      # type: ignore[arg-type]
            content="You are a helpful assistant.",
            created_at=now,
        )


# ── WorkflowState ─────────────────────────────────────────────────────────────

def test_workflow_state_constructed_with_all_fields(
    minimal_agent_call: AgentCall,
    source: Source,
    now: datetime,
) -> None:
    """WorkflowState can be instantiated as a plain TypedDict with all fields."""
    turn = ConversationTurn(role="user", content="Hello", created_at=now)

    state: WorkflowState = {
        "query": "Who are Celonis competitors?",
        "session_id": None,
        "agent_calls": [minimal_agent_call],
        "decomposed_tasks": [{"capability": "web_search", "params": {}}],
        "retrieved_context": ["Celonis is a process mining company..."],
        "conversation_history": [turn],
        "validation_results": [],
        "sources": [source],
        "derivation": "Synthesised from retrieved context",
        "final_output": "SAP, IBM, and UiPath are key competitors.",
    }

    assert state["query"] == "Who are Celonis competitors?"
    assert len(state["agent_calls"]) == 1
    assert state["agent_calls"][0].capability == "web_search"
    assert state["conversation_history"][0].role == "user"
    assert state["final_output"] != ""