"""backend/app/orchestration/nodes/retrieve.py

Retrieve node — runs hybrid RAG search and writes top results into
WorkflowState.retrieved_context.

Keep this node thin: one call to search_chunks, one state update.
No prompt logic here.

Issue #60: Retrieve node — hybrid RAG lookup with metadata pre-filter
"""

from app.orchestration.state import WorkflowState
from app.rag import search_chunks


async def retrieve_node(state: WorkflowState) -> dict:
    """Run hybrid search and write chunk content to retrieved_context.

    Returns a dict with only the keys being updated — LangGraph merges
    it into the full state.
    """
    results = search_chunks(query=state["query"], limit=10)
    return {"retrieved_context": [chunk.content for chunk in results]}