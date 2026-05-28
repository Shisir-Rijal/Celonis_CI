"""backend/app/orchestration/graph.py

Defines the orchestrator LangGraph StateGraph.
Keep this file thin — it only wires nodes and edges.
Logic lives in the individual node files.

Each subsequent issue adds the next node and connects it
with builder.add_edge.

Issue #59: orchestrator graph scaffold and Memory Load node
"""

from langgraph.graph import StateGraph

from app.orchestration.nodes.memory_load import memory_load_node
from app.orchestration.state import WorkflowState

# ── Build graph ───────────────────────────────────────────────────────
builder = StateGraph(WorkflowState)

# ── Nodes ─────────────────────────────────────────────────────────────
builder.add_node("memory_load", memory_load_node)

# ── Entry point ───────────────────────────────────────────────────────
builder.set_entry_point("memory_load")

# ── Compile ───────────────────────────────────────────────────────────
orchestrator_graph = builder.compile()