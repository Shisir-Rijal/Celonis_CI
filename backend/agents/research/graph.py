# Definiert welche Nodes in welcher Reihenfolge ausgeführt werden.


from langgraph.graph import END, StateGraph

# Define a new Graph
graph = StateGraph(AgentState)

graph.add_node("financials", financials_function)
graph.add_node("seo", seo_function)

graph.set_entry_point("start")

graph.add_conditional_edges(
    "agent",
    conditional_function,
    {
        "continue" : "action", # Key needs to match output of conditional_function
        "end": END
    }
)
graph.add_edge("branding", END)

app = graph.compile() # Compination into LangChain Runnable