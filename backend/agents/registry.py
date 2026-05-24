# mappt Agent-Namen zu Graph-Instanzen

AGENTS = {
    "research": research.graph.compile(),
}

def get_agent(name: str): return AGENTS[name]
