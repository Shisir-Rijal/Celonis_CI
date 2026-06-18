"""backend/app/orchestration/graph.py

Defines the orchestrator LangGraph StateGraph.
Keep this file thin — it only wires nodes and edges.
Logic lives in the individual node files.

Issue #59: initial scaffold + Memory Load node
Issue #60: added Retrieve node
Issue #61: added Assessment node, agentic_retrieve stub, dispatch stub,
           conditional edge after assess
Issue #63: replaced dispatch stub with real dispatch, added correlation stub,
           synthesize stub, conditional edge dispatch → (correlation | synthesize)
"""

from langgraph.graph import END, StateGraph

from app.orchestration.nodes.agentic_retrieve import agentic_retrieve_node
from app.orchestration.nodes.assess import assess_node
from app.orchestration.nodes.correlation import correlation_node
from app.orchestration.nodes.dispatch import dispatch_node, should_correlate
from app.orchestration.nodes.memory_load import memory_load_node
from app.orchestration.nodes.retrieve import retrieve_node
from app.orchestration.nodes.synthesize import synthesize_node
from app.orchestration.state import WorkflowState
from app.orchestration.nodes.critic import critic_node
from app.orchestration.nodes.respond import respond_node

# ── Capability modules ────────────────────────────────────────────────
import app.agents.research.nodes.news  # noqa: F401 — registers fetch_news capability at startup


def _route_after_assess(state: WorkflowState) -> str:
    """Route to dispatch for standard queries, agentic_retrieve for discovery."""
    if state.get("retrieval_mode") == "agentic":
        return "agentic_retrieve"
    return "dispatch"


# ── Build graph ───────────────────────────────────────────────────────
builder = StateGraph(WorkflowState)

# ── Nodes ─────────────────────────────────────────────────────────────
builder.add_node("memory_load", memory_load_node)
builder.add_node("retrieve", retrieve_node)
builder.add_node("assess", assess_node)
builder.add_node("agentic_retrieve", agentic_retrieve_node)
# TODO: add edge agentic_retrieve → dispatch (Phase 2) so the agentic path
# completes end-to-end. Currently the graph terminates after agentic_retrieve.
builder.add_node("dispatch", dispatch_node)
builder.add_node("correlation", correlation_node)
builder.add_node("synthesize", synthesize_node)
builder.add_node("critic", critic_node)
builder.add_node("respond", respond_node)

# ── Entry point ───────────────────────────────────────────────────────
builder.set_entry_point("memory_load")

# ── Edges ─────────────────────────────────────────────────────────────
builder.add_edge("memory_load", "retrieve")
builder.add_edge("retrieve", "assess")
builder.add_edge("correlation", "synthesize")
builder.add_conditional_edges(
    "assess",
    _route_after_assess,
    {
        "dispatch": "dispatch",
        "agentic_retrieve": "agentic_retrieve",
    },
)
builder.add_conditional_edges(
    "dispatch",
    should_correlate,
    {
        "correlation": "correlation",
        "synthesize": "synthesize",
    },
)
builder.add_edge("synthesize", "critic")
builder.add_edge("critic", "respond")
builder.add_edge("respond", END)

# ── Compile ───────────────────────────────────────────────────────────
orchestrator_graph = builder.compile()