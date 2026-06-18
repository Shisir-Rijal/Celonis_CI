"""backend/app/agents/brand/state.py

State schema for the Brand Intelligence Pipeline.

BrandPipelineState is the shared object that flows through the LangGraph
fan-out. load_profile populates profile from Nadja's Research Agent.
Each capability node reads from profile and writes its name to
completed_capabilities when done.

Issue #86: Brand Intelligence Pipeline — LangGraph foundation and manual runner
"""

from typing import TypedDict, Annotated, Any
import operator

from app.agents.research.state import CompetitorProfile


class BrandPipelineState(TypedDict):
    """Shared state for the Brand Intelligence Pipeline graph.

    Fields
    ------
    competitor_domain:
        The domain to analyse, e.g. "sap.com". Passed in by the runner.
    nodes_to_run:
        Which Research Agent nodes to call inside load_profile.
        Empty list means all nodes (default behaviour).
        Example: ["seogeo"] to only load GEO/SEO data for AI-Search Coherence.
    profile:
        Populated by load_profile after calling the selected Research nodes.
        None until load_profile completes successfully.
    results:
        Capability outputs keyed by capability name. Each capability node
        writes its structured result here.
    errors:
        Additive list — each node appends its own errors without overwriting
        errors from other nodes.
    completed_capabilities:
        Additive list — each capability node appends its name on success.
    """

    competitor_domain: str
    nodes_to_run: list[str]
    profile: CompetitorProfile | None
    results: dict[str, Any]
    errors: Annotated[list[str], operator.add]
    completed_capabilities: Annotated[list[str], operator.add]
