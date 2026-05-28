"""backend/app/orchestration/graph.py

Defines the orchestrator LangGraph StateGraph.
Keep this file thin — it only wires nodes and edges.
Logic lives in the individual node files.

Issue #59: initial scaffold + Memory Load node
Issue #60: added Retrieve node
"""

from langgraph.graph import StateGraph

from app.orchestration.nodes.memory_load import memory_load_node
from app.orchestration.nodes.retrieve import retrieve_node
from app.orchestration.state import WorkflowState

# ── Build graph ───────────────────────────────────────────────────────
builder = StateGraph(WorkflowState)

# ── Nodes ─────────────────────────────────────────────────────────────
builder.add_node("memory_load", memory_load_node)
builder.add_node("retrieve", retrieve_node)

# ── Entry point ───────────────────────────────────────────────────────
builder.set_entry_point("memory_load")

# ── Edges ─────────────────────────────────────────────────────────────
builder.add_edge("memory_load", "retrieve")

# ── Compile ───────────────────────────────────────────────────────────
orchestrator_graph = builder.compile()
