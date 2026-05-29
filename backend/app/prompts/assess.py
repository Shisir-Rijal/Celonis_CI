"""backend/app/prompts/assess.py

Prompt template for the Assessment node.
Capability list is hardcoded here — replaced by Capability Registry in Issue #62.

Issue #61: Assessment node — LLM query decomposition into capability tasks
"""

from app.orchestration.state import ConversationTurn
from app.orchestration.capability_registry import get_capability_list

# Hardcoded for now — replaced by @register_capability in Issue #62


_SYSTEM_TEMPLATE = """\
You are the Assessment agent for a brand intelligence system.
Analyse the user query and decide which capabilities should handle it.

AVAILABLE CAPABILITIES:
{capabilities}

OUTPUT FORMAT — respond with valid JSON only, no markdown, no explanation:
{{
  "tasks": [
    {{"capability": "<name>", "params": {{"<key>": "<value>"}}}}
  ],
  "retrieval_mode": "standard",
  "discovery_query": null
}}

RULE — Comparison queries:
If the query explicitly compares or contrasts two known entities,
create ONE task per entity using the same capability.
NEVER bundle multiple companies into a single task's params.
Example: "Compare SAP and Celonis Q1 messaging"
→ [{{"capability":"wording_analysis","params":{{"company":"Celonis"}}}},
   {{"capability":"wording_analysis","params":{{"company":"SAP"}}}}]

RULE — Discovery queries (unknown entity):
If the query asks about unknown parties ("who reacted", "what did analysts say",
"how did the market respond"), set retrieval_mode="agentic" and
discovery_query to the sub-query that retrieves the anchor document.
Example: "How did analysts react to Celonis' Q1 report?"
→ retrieval_mode="agentic", discovery_query="Celonis Q1 2026 report"

When retrieval_mode is "agentic": tasks must be [] and discovery_query must be set.
When retrieval_mode is "standard": discovery_query must be null.\
"""


def build_system_message() -> dict:
    """Return the system message with capabilities from the registry."""
    cap_list = get_capability_list()
    capabilities = (
        "\n".join(f"- {c['name']}: {c['description']}" for c in cap_list)
        if cap_list
        else "(no capabilities registered)"
    )
    return {
        "role": "system",
        "content": _SYSTEM_TEMPLATE.format(capabilities=capabilities),
    }


def build_user_message(
    query: str,
    retrieved_context: list[str],
    conversation_history: list[ConversationTurn],
) -> dict:
    """Build the user message with query, last 3 turns, and top-5 context chunks."""

    # Last 3 conversation turns
    recent = conversation_history[-3:] if conversation_history else []
    turns_text = (
        "\n".join(f"{t.role.upper()}: {t.content}" for t in recent)
        if recent
        else "(no prior conversation)"
    )

    # Top-5 retrieved context chunks, truncated to ~200 chars each
    top_chunks = retrieved_context[:5]
    chunks_text = (
        "\n\n".join(
            f"[{i + 1}] {chunk[:200]}{'...' if len(chunk) > 200 else ''}"
            for i, chunk in enumerate(top_chunks)
        )
        if top_chunks
        else "(no retrieved context)"
    )

    content = f"""\
CONVERSATION HISTORY (last 3 turns):
{turns_text}

RETRIEVED CONTEXT (top 5 chunks):
{chunks_text}

USER QUERY:
{query}

Respond with JSON only."""

    return {"role": "user", "content": content}