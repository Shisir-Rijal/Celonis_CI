"""backend/app/orchestration/nodes/synthesize.py

Synthesize node — assemble final answer, sources, and derivation.

Handles three cases:
  0 successful AgentCalls → fall back to retrieved_context for a direct RAG answer
  1 successful AgentCall  → format its output directly
  2+ successful AgentCalls → LLM writes a narrative combining them (Writer role)

Issue #64: Synthesize node — assemble final answer, sources, and derivation
"""

import json

from app.exceptions import SynthesisError
from app.llm import get_chat_client
from app.models.schemas import Source
from app.orchestration.state import AgentCall, WorkflowState
from app.prompts.synthesize import (
    build_multi_capability_messages,
    build_no_capabilities_messages,
    build_single_capability_messages,
)


async def synthesize_node(state: WorkflowState) -> dict:
    """Produce the final answer, sources, and derivation from AgentCall results.

    Returns a dict updating:
      - final_output: str
      - sources: list[Source]
      - derivation: str
    """
    agent_calls: list[AgentCall] = state["agent_calls"]
    retrieved_context: list[str] = state["retrieved_context"]
    query: str = state["query"]

    successful = [c for c in agent_calls if c.error is None]

    # ── Unhappy path: nothing to work with ────────────────────────────
    if not successful and not retrieved_context:
        return {
            "final_output": "No relevant information found.",
            "sources": [],
            "derivation": "",
        }

    # ── Source deduplication (last-write-wins on URL) ─────────────────
    sources: list[Source] = list(
        {s.url: s for c in successful for s in c.sources}.values()
    )

    # ── Build messages for the appropriate case ───────────────────────
    if not successful:
        messages = build_no_capabilities_messages(
            query, retrieved_context
        )
    elif len(successful) == 1:
        messages = build_single_capability_messages(
            query, successful[0]
        )
    else:
        messages = build_multi_capability_messages(
            query, successful
        )

    # ── LLM call ──────────────────────────────────────────────────────
    client = get_chat_client()
    raw = await client.complete(messages)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SynthesisError(
            f"LLM returned malformed JSON: {exc}\nRaw: {raw!r}"
        ) from exc

    return {
        "final_output": parsed.get("answer", ""),
        "sources": sources,
        "derivation": parsed.get("derivation", ""),
    }