"""backend/app/agents/sov/graph.py

Share-of-Voice agent — LangGraph wiring.

Execution order is strictly linear:
  START → load_mentions → classify → persist → END

State merging (errors, etc.) is handled by LangGraph based on the
Annotated[..., operator.add] hints on SovPipelineState fields.

The graph is compiled once at module import time. Importers reuse the
same compiled object via `sov_graph`.
"""

from langgraph.graph import END, START, StateGraph

from app.agents.sov.nodes.classify import classify_node
from app.agents.sov.nodes.load_mentions import load_mentions_node
from app.agents.sov.nodes.persist import persist_node
from app.agents.sov.state import SovPipelineState


# ---------------------------------------------------------------------------
# Graph wiring
# ---------------------------------------------------------------------------

builder = StateGraph(SovPipelineState)

# Nodes
builder.add_node("load_mentions", load_mentions_node)
builder.add_node("classify", classify_node)
builder.add_node("persist", persist_node)

# Edges — linear pipeline
builder.add_edge(START, "load_mentions")
builder.add_edge("load_mentions", "classify")
builder.add_edge("classify", "persist")
builder.add_edge("persist", END)

# Compile once at import — reuse for every run
sov_graph = builder.compile()
