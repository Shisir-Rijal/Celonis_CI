"""backend/app/orchestration/nodes/memory_load.py

Memory Load node — first node in the orchestrator graph.
Loads conversation history from Supabase into WorkflowState so all
downstream nodes have the full conversation context available.

Issue #59: orchestrator graph scaffold and Memory Load node
"""

from app.orchestration.memory import load_conversation_history
from app.orchestration.state import WorkflowState


async def memory_load_node(state: WorkflowState) -> dict:
    """Load conversation history from Supabase into WorkflowState.

    Returns a dict with only the keys being updated — LangGraph merges
    it into the full state.

    If session_id is None, returns empty history without calling the
    repository or raising.
    """
    session_id = state["session_id"]

    if session_id is None:
        return {"conversation_history": []}

    turns = load_conversation_history(session_id, limit=10)
    return {"conversation_history": turns}