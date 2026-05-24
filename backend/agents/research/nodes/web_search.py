# Web sracping


async def web_search_node(state: AgentState) -> dict:
    results = await serper_client.search(state["competitor_domain"])
    return {"company_name": results["name"]}   # nur das Feld das dieser Node kennt
