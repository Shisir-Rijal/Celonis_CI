"""backend/app/orchestration/state.py

Defines WorkflowState (TypedDict — LangGraph requires TypedDict for state)
and the AgentCall / ConversationTurn Pydantic models used as structured
sub-objects within that state.

Issue #57: extend WorkflowState with conversation history and structured
AgentCall schema.
"""

from __future__ import annotations
from uuid import UUID
from datetime import datetime
from typing import Any, Literal, TypedDict
from uuid import UUID

from pydantic import BaseModel

from app.models.schemas import Source


class AgentCall(BaseModel):
    """Records a single capability invocation within a workflow turn."""

    capability: str
    input_params: dict[str, Any]
    output: dict[str, Any]
    sources: list[Source]
    derivation: str
    persist_to_rag: bool = False
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class ConversationTurn(BaseModel):
    """A single exchange in the conversation history."""

    role: Literal["user", "assistant"]
    content: str
    sources: list[Source] = []
    derivation: str = ""
    created_at: datetime

class WorkflowState(TypedDict):
    """Shared state passed between every node in the orchestrator graph.

    LangGraph requires TypedDict (not BaseModel) at the top level.
    Nested structured objects (AgentCall, ConversationTurn) use BaseModel
    so they can be serialised cleanly for storage and transport.
    """

    # ── Input ────────────────────────────────────────────────────
    session_id: UUID | None # Session context (added in Issue #59)
    query: str

    # ── Agent bookkeeping ────────────────────────────────────────
    agent_calls: list[AgentCall]
    decomposed_tasks: list[dict[str, Any]]

    # ── Retrieval ────────────────────────────────────────────────
    retrieved_context: list[str]

    # ── Conversation memory ──────────────────────────────────────
    conversation_history: list[ConversationTurn]

    # ── Validation ───────────────────────────────────────────────
    validation_results: list[str]

    # ── Synthesis output ─────────────────────────────────────────
    sources: list[Source]   # deduplicated sources for the answer
    derivation: str         # how the final answer was derived
    final_output: str       # the answer returned to the user

    # Assessment output (added in Issue #61)
    retrieval_mode: str          # "standard" | "agentic"
    discovery_query: str | None  # set only when retrieval_mode == "agentic"
