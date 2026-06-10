import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from typing import Any, Callable
from langgraph.graph import START, END, StateGraph
from app.agents.research.state import ResearchState
from app.agents.research.nodes import (
    news, financials, visuals, positioning,
    socials, seogeo, events, newsletter, youtube, wording,
)


def _build(node_map: dict[str, Callable]) -> Any:
    g = StateGraph(ResearchState)
    for name, fn in node_map.items():
        g.add_node(name, fn)
        g.add_edge(START, name)
        g.add_edge(name, END)
    return g.compile()


# --- Tier graphs — invoke the matching graph on each cadence ---

daily_graph = _build({
    "financials": financials.run,
})

weekly_graph = _build({
    "news": news.run,
})

monthly_graph = _build({
    "events":     events.run,
    "seogeo":     seogeo.run,
    "newsletter": newsletter.run,
    "youtube":    youtube.run,
})

semiannual_graph = _build({
    "visuals":     visuals.run,
    "positioning": positioning.run,
    "socials":     socials.run,
    "wording":     wording.run,   # stub — replace once wording.py is implemented
})


if __name__ == "__main__":
    import asyncio
    import structlog
    structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

    async def main():
        # Minimal initial state — tier graphs only write their own keys
        initial_state: ResearchState = {
            "competitor_domain": "celonis.com",
            "errors": [],
            "completed_nodes": [],
        }
        result = await daily_graph.ainvoke(initial_state)
        print("Completed:", result["completed_nodes"])
        print("Errors:",    result["errors"])
        if result.get("financials"):
            print(result["financials"].model_dump_json(indent=2))

    asyncio.run(main())
