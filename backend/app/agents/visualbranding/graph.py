"""backend/app/agents/visualbranding/graph.py

Visual Branding Interpretation Pipeline — LangGraph change-gated fan-out
with an alerts fan-in.

Unlike the per-competitor research/brand pipelines, this graph runs once
globally across all tracked competitors. Before doing any (expensive,
LLM-backed) interpretation, `detect_changes_node` compares the current
fingerprint of each raw dimension (colors/fonts/logo/images/videos — all
sourced from research_snapshots' "visuals" node) against the fingerprint
recorded the last time each visualbranding node ran. Only dimensions whose
source data actually changed get routed to their node — everything else is
skipped at the graph level, not just gated inside the node.

Every interpretation node that does run also diffs its new analysis against
its own previous run (see alerts.py) and contributes change fragments. Three
independent fan-ins follow: `build_alerts_node` assembles those fragments
into one AlertAnalysis, `trends` (nodes/trends.py) turns them into a
per-element up/down/flat summary, and `brand_archetypes` (nodes/archetypes.py)
synthesizes a holistic per-company brand archetype from every dimension's
latest persisted analysis — all three persisted the same way as every other
node's output.
"""

from datetime import datetime, timezone

import structlog

from langgraph.graph import END, START, StateGraph

from app.agents.visualbranding.nodes import archetypes, colors, fixed_archetypes, fonts, images, logos, trends, videos
from app.agents.visualbranding.repositories.visualbranding_repository import (
    compute_fingerprint,
    get_latest_fingerprint,
    insert_visualbranding_snapshot,
)
from app.agents.visualbranding.source_data import (
    extract_dimension,
    get_latest_visuals_by_domain,
)
from app.agents.visualbranding.state import AlertAnalysis, VisualBrandingState

logger = structlog.get_logger(__name__)

# Raw VisualsData field -> visualbranding node that interprets it.
DIMENSION_TO_NODE = {
    "colors": "colors",
    "fonts": "fonts",
    "logo": "logos",
    "images": "images",
    "videos": "videos",
}

# A node only belongs here once it's actually implemented — having a
# DIMENSION_TO_NODE entry isn't enough, it also needs a real nodes/<name>.py,
# an add_node() call, and edges in/out below.
IMPLEMENTED_NODES = {"colors", "fonts", "logos", "images", "videos"}


# ---------------------------------------------------------------------------
# Node: detect_changes (router)
# ---------------------------------------------------------------------------

async def detect_changes_node(state: VisualBrandingState) -> dict:
    """Compare each dimension's current source fingerprint against the
    fingerprint recorded the last time its node ran. Sets state["changed_nodes"]
    for `route_changed_nodes` to act on."""
    visuals_by_domain = await get_latest_visuals_by_domain()

    changed: list[str] = []
    for dimension, node_name in DIMENSION_TO_NODE.items():
        current_fp = compute_fingerprint(extract_dimension(visuals_by_domain, dimension))
        last_fp = get_latest_fingerprint(node_name)
        if current_fp != last_fp:
            changed.append(node_name)

    logger.info("visualbranding_changes_detected", changed=changed)
    return {"changed_nodes": changed}


def route_changed_nodes(state: VisualBrandingState) -> list[str]:
    """Fan out only to nodes whose source data changed AND are implemented.
    Routes straight to END if nothing changed (or nothing changed is
    implemented yet) — no node runs needlessly, and build_alerts never runs
    either, so AlertAnalysis simply isn't refreshed that round."""
    changed = state.get("changed_nodes", [])
    targets = [n for n in changed if n in IMPLEMENTED_NODES]
    if not targets:
        logger.info("visualbranding_no_changes", skipped=changed)
        return [END]
    return targets


# ---------------------------------------------------------------------------
# Node: build_alerts (fan-in)
# ---------------------------------------------------------------------------

async def build_alerts_node(state: VisualBrandingState) -> dict:
    """Once every interpretation node that ran this round has finished,
    collect their alert fragments into one AlertAnalysis and persist it —
    gives the frontend one place to show "what changed since last time"
    across every dimension. Fields stay None where nothing meaningful
    changed (or that node didn't run this round)."""
    alerts = AlertAnalysis(
        color=state.get("color_alerts") or None,
        font=state.get("font_alerts") or None,
        logo=state.get("logo_alerts") or None,
        image=state.get("image_alerts") or None,
        video=state.get("video_alerts") or None,
        trend=state.get("trend_alerts") or None,
    )
    run_at = datetime.now(timezone.utc)
    try:
        fingerprint = compute_fingerprint(alerts.model_dump(mode="json"))
        insert_visualbranding_snapshot("alerts", run_at, fingerprint, alerts)
        logger.info("visualbranding_alerts_persisted")
    except Exception as exc:
        logger.error("visualbranding_alerts_persist_failed", error=str(exc))
    return {"alerts": alerts}


# ---------------------------------------------------------------------------
# Graph wiring
# ---------------------------------------------------------------------------

builder = StateGraph(VisualBrandingState)

builder.add_node("detect_changes", detect_changes_node)
builder.add_node("colors", colors.run)
builder.add_node("fonts", fonts.run)
builder.add_node("logos", logos.run)
builder.add_node("images", images.run)
builder.add_node("videos", videos.run)
builder.add_node("build_alerts", build_alerts_node)
builder.add_node("trends", trends.run)
builder.add_node("brand_archetypes", archetypes.run)
builder.add_node("fixed_archetypes", fixed_archetypes.run)

builder.add_edge(START, "detect_changes")
builder.add_conditional_edges(
    "detect_changes",
    route_changed_nodes,
    {
        "colors": "colors",
        "fonts": "fonts",
        "logos": "logos",
        "images": "images",
        "videos": "videos",
        END: END,
    },
)
# Fan-in: build_alerts, trends, brand_archetypes, and fixed_archetypes all
# run once every interpretation node that was scheduled this round has
# finished — independent of each other.
for node_name in ("colors", "fonts", "logos", "images", "videos"):
    builder.add_edge(node_name, "build_alerts")
    builder.add_edge(node_name, "trends")
    builder.add_edge(node_name, "brand_archetypes")
    builder.add_edge(node_name, "fixed_archetypes")
builder.add_edge("build_alerts", END)
builder.add_edge("trends", END)
builder.add_edge("brand_archetypes", END)
builder.add_edge("fixed_archetypes", END)

visualbranding_graph = builder.compile()
