"""backend/app/orchestration/nodes/respond.py

Respond node — final node in the orchestrator graph.
Persists the completed turn to conversation memory.

Issue #66: Respond node and SSE chat endpoint — orchestrator end-to-end
"""

import structlog

from app.orchestration.memory import save_turn
from app.orchestration.state import WorkflowState

logger = structlog.get_logger(__name__)


async def respond_node(state: WorkflowState) -> dict:
    """Save the completed turn to conversation memory.

    save_turn raising does NOT abort the response — the answer has already
    been produced. Log the error and continue.
    """
    session_id = state.get("session_id")
    if session_id is None:
        logger.warning("respond_node_no_session_id")
        return {}

    try:
        save_turn(
            session_id=session_id,
            query=state["query"],
            answer=state["final_output"],
            sources=state["sources"],
            derivation=state["derivation"],
        )
    except Exception as exc:
        logger.error("respond_node_save_turn_failed", error=str(exc))

    return {}