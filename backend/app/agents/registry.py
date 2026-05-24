# mappt Agent-Namen zu Graph-Instanzen
from app.agents.research.graph import app as research_graph

AGENTS = {
    "research": research_graph,
}

def get_agent(name: str): return AGENTS[name]
