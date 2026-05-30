"""backend/app/prompts/synthesize.py

Prompt templates for the Synthesize node — three cases.
Each instructs the LLM to return {"answer": str, "derivation": str}.

Issue #64: Synthesize node — assemble final answer, sources, and derivation
"""

import json as _json

from app.orchestration.state import AgentCall

# ── System prompts ────────────────────────────────────────────────────

PROMPT_NO_CAPABILITIES = """\
You are a brand intelligence assistant.
No structured capability analysis is available for this query.
Answer using only the retrieved context passages provided.
Return a JSON object with exactly these two keys:
  "answer": your answer as a plain string
  "derivation": a one-sentence explanation of how you derived the answer
If the context contains no useful information, say so in the answer.
Respond with JSON only — no markdown, no explanation outside the JSON.\
"""

PROMPT_SINGLE_CAPABILITY = """\
You are a brand intelligence assistant.
One capability analysis has been completed for this query.
Use the capability output and its derivation to write a clear, concise final answer.
Return a JSON object with exactly these two keys:
  "answer": your formatted answer as a plain string
  "derivation": a one-sentence explanation citing the capability used
Respond with JSON only — no markdown, no explanation outside the JSON.\
"""

PROMPT_MULTI_CAPABILITY = """\
You are a brand intelligence writer.
Multiple capability analyses have been completed for this query.
Write a single coherent narrative answer that combines all results.
Return a JSON object with exactly these two keys:
  "answer": your narrative answer as a plain string combining all results
  "derivation": a one-sentence explanation of how you synthesised the sources
Respond with JSON only — no markdown, no explanation outside the JSON.\
"""


# ── Message builders ──────────────────────────────────────────────────

def build_no_capabilities_messages(
    query: str,
    retrieved_context: list[str],
) -> list[dict]:
    """Messages for the 0-successful-calls case: answer from retrieved context."""
    context_text = "\n\n".join(
        f"[{i + 1}] {chunk[:500]}" for i, chunk in enumerate(retrieved_context[:5])
    ) or "(no retrieved context)"

    user_content = (
        f"QUERY: {query}\n\n"
        f"RETRIEVED CONTEXT:\n{context_text}\n\n"
        f"Respond with JSON only."
    )
    return [
        {"role": "system", "content": PROMPT_NO_CAPABILITIES},
        {"role": "user", "content": user_content},
    ]


def build_single_capability_messages(
    query: str,
    call: AgentCall,
) -> list[dict]:
    """Messages for the 1-successful-call case."""
    output_json = _json.dumps(call.output, default=str)
    user_content = (
        f"QUERY: {query}\n\n"
        f"CAPABILITY: {call.capability}\n"
        f"OUTPUT:\n{output_json}\n"
        f"DERIVATION: {call.derivation}\n\n"
        f"Respond with JSON only."
    )
    return [
        {"role": "system", "content": PROMPT_SINGLE_CAPABILITY},
        {"role": "user", "content": user_content},
    ]


def build_multi_capability_messages(
    query: str,
    calls: list[AgentCall],
) -> list[dict]:
    """Messages for the 2+-successful-calls case (Writer role)."""
    outputs = []
    for i, call in enumerate(calls, 1):
        output_json = _json.dumps(call.output, default=str)
        outputs.append(
            f"[{i}] CAPABILITY: {call.capability}\n"
            f"OUTPUT:\n{output_json}\n"
            f"DERIVATION: {call.derivation}"
        )
    outputs_text = "\n\n".join(outputs)

    user_content = (
        f"QUERY: {query}\n\n"
        f"CAPABILITY OUTPUTS:\n{outputs_text}\n\n"
        f"Respond with JSON only."
    )
    return [
        {"role": "system", "content": PROMPT_MULTI_CAPABILITY},
        {"role": "user", "content": user_content},
    ]