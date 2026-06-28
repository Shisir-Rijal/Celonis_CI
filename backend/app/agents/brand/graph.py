"""backend/app/agents/brand/graph.py

Brand Intelligence Pipeline — LangGraph fan-out graph.

Execution order:
  1. load_profile: calls selected Research Agent nodes, builds CompetitorProfile
  2. All capability nodes start in parallel from load_profile
  3. Each capability node writes its results to Supabase and returns to END

Issue #86: Brand Intelligence Pipeline — LangGraph foundation and manual runner
"""

import structlog

from langgraph.graph import START, END, StateGraph

from app.agents.brand.nodes.geo_intelligence import geo_intelligence_node
from app.agents.brand.state import BrandPipelineState
from app.agents.research.state import CompetitorProfile

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Node: load_profile
# ---------------------------------------------------------------------------

async def load_profile_node(state: BrandPipelineState) -> dict:
    """Build a CompetitorProfile for the given competitor domain.

    Capability nodes only need profile.domain. Research node data
    (seogeo, news, etc.) is loaded on demand by each capability node
    once the research pipeline is wired up end-to-end.

    Returns {"profile": CompetitorProfile} on success.
    Returns {"errors": [...]} on failure.
    """
    domain = state["competitor_domain"]
    logger.info("load_profile_started", domain=domain)

    try:
        profile = CompetitorProfile(domain=domain)
        logger.info("load_profile_done", domain=domain)
        return {"profile": profile}

    except Exception as exc:
        logger.error("load_profile_failed", domain=domain, error=str(exc))
        return {"errors": [f"load_profile: {exc}"]}


# ---------------------------------------------------------------------------
# Graph wiring
# ---------------------------------------------------------------------------

builder = StateGraph(BrandPipelineState)

# Nodes
builder.add_node("load_profile", load_profile_node)
builder.add_node("geo_intelligence", geo_intelligence_node)

# Edges — load_profile first, then fan-out to capability nodes
builder.add_edge(START, "load_profile")
builder.add_edge("load_profile", "geo_intelligence")
builder.add_edge("geo_intelligence", END)

# Compile
brand_graph = builder.compile()