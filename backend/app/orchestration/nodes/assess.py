"""backend/app/orchestration/nodes/assess.py

Assessment node — uses the LLM to decompose the user query into
capability tasks and classify the retrieval mode.

Issue #61: Assessment node — LLM query decomposition into capability tasks
"""

import json

from app.exceptions import AssessmentError
from app.llm import get_chat_client
from app.orchestration.state import WorkflowState
from app.prompts.assess import build_system_message, build_user_message


async def assess_node(state: WorkflowState) -> dict:
    """Decompose the user query into capability tasks.

    Reads state["query"], state["retrieved_context"],
    state["conversation_history"] and calls the LLM.

    Returns a dict updating:
      - decomposed_tasks: list[dict]
      - retrieval_mode: "standard" | "agentic"
      - discovery_query: str | None
    """
    client = get_chat_client()

    messages = [
        build_system_message(),
        build_user_message(
            query=state["query"],
            retrieved_context=state["retrieved_context"],
            conversation_history=state["conversation_history"],
        ),
    ]

    raw = await client.complete(messages)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AssessmentError(
            f"LLM returned malformed JSON: {exc}\nRaw response: {raw!r}"
        ) from exc

    retrieval_mode = parsed.get("retrieval_mode", "standard")
    discovery_query = parsed.get("discovery_query")
    tasks = parsed.get("tasks", [])

    # Validate: agentic mode must have discovery_query
    if retrieval_mode == "agentic" and not discovery_query:
        raise AssessmentError(
            "LLM returned retrieval_mode='agentic' but discovery_query "
            "is missing or empty."
        )

    return {
        "decomposed_tasks": tasks,
        "retrieval_mode": retrieval_mode,
        "discovery_query": discovery_query,
    }