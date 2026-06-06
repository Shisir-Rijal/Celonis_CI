"""backend/app/agents/brand/graph.py

Brand Intelligence Pipeline — LangGraph fan-out graph.

Execution order:
  1. load_profile: calls selected Research Agent nodes, builds CompetitorProfile
  2. All capability nodes start in parallel from load_profile
  3. Each capability node writes its results to Supabase and returns to END

Issue #86: Brand Intelligence Pipeline — LangGraph foundation and manual runner
"""

import asyncio
import structlog

from langgraph.graph import START, END, StateGraph

from app.agents.brand.state import BrandPipelineState
from app.agents.research.nodes import seogeo
from app.agents.research.state import (
    ResearchState,
    CompetitorProfile,
    SeoGeoData,
    NewsData,
    VisualsData,
    PositioningData,
    FinancialData,
    SocialData,
    EventsData,
    NewsletterData,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Node: load_profile
# ---------------------------------------------------------------------------

async def load_profile_node(state: BrandPipelineState) -> dict:
    """Call selected Research Agent nodes and build a CompetitorProfile.

    Reads state["competitor_domain"] and state["nodes_to_run"].
    For Phase 1 only seogeo is supported. Extend NODE_MAP as new
    capabilities are added.

    Returns {"profile": CompetitorProfile} on success.
    Returns {"errors": [...]} on failure — graph continues with profile=None.
    """
    domain = state["competitor_domain"]
    logger.info("load_profile_started", domain=domain)

    try:
        research_state = ResearchState(
            competitor_domain=domain,
            visuals=VisualsData(),
            positioning=PositioningData(),
            financials=FinancialData(),
            socials=SocialData(),
            seogeo=SeoGeoData(),
            news=NewsData(),
            events=EventsData(),
            newsletter=NewsletterData(),
            errors=[],
            completed_nodes=[],
        )

        result = await seogeo.run(research_state)

        profile = CompetitorProfile(
            domain=domain,
            seogeo=result.get("seogeo"),
        )

        logger.info("load_profile_done", domain=domain)
        return {"profile": profile}

    except Exception as exc:
        logger.error("load_profile_failed", domain=domain, error=str(exc))
        return {"errors": [f"load_profile: {exc}"]}


# ---------------------------------------------------------------------------
# Node: ai_search_coherence (stub — real logic in separate issue)
# ---------------------------------------------------------------------------

async def ai_search_coherence_node(state: BrandPipelineState) -> dict:
    """AI-Search Coherence capability — stub.

    TODO: implement real logic in AI-Search Coherence issue.
    Reads state["profile"].seogeo.geo and writes results to Supabase.
    """
    # TODO: replace with real implementation
    return {"completed_capabilities": ["ai_search_coherence"]}


# ---------------------------------------------------------------------------
# Graph wiring
# ---------------------------------------------------------------------------

builder = StateGraph(BrandPipelineState)

# Nodes
builder.add_node("load_profile", load_profile_node)
builder.add_node("ai_search_coherence", ai_search_coherence_node)

# Edges — load_profile first, then fan-out to capability nodes
builder.add_edge(START, "load_profile")
builder.add_edge("load_profile", "ai_search_coherence")
builder.add_edge("ai_search_coherence", END)

# Compile
brand_graph = builder.compile()