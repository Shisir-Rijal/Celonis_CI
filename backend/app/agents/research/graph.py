import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from langgraph.graph import START, END, StateGraph
from app.agents.research.state import ResearchState
from app.agents.research.nodes import news, financials, visuals, positioning, socials, seogeo, events, newsletter, sociallinks

# Wöchentlich scrapen und manche stündlich oder täglich

graph = StateGraph(ResearchState)

graph.add_node("financials", financials.run)
graph.add_node("seogeo", seogeo.run)
graph.add_node("news", news.run)
graph.add_node("socials", socials.run)
graph.add_node("positioning", positioning.run)
graph.add_node("visuals", visuals.run)
graph.add_node("events", events.run)
graph.add_node("newsletter", newsletter.run)

for node in ["financials", "seogeo", "news", "socials", "positioning", "visuals", "events", "newsletter"]:
    graph.add_edge(START, node)
    graph.add_edge(node, END)

app = graph.compile()


if __name__ == "__main__":
    import asyncio
    from app.agents.research.state import CompetitorProfile
    import structlog
    structlog.configure(
        processors=[
            structlog.dev.ConsoleRenderer()
        ]
    )

    async def main():
        initial_state = ResearchState(
            competitor_domain="celonis.com",
            profile=CompetitorProfile(domain="celonis.com"),
            errors=[],
            completed_nodes=[],
        )
        result = await app.ainvoke(initial_state)
        print("Completed:", result["completed_nodes"])
        print("Errors:", result["errors"])

    asyncio.run(main())
