"""Not a permanent script -- delete after use."""
import truststore
truststore.inject_into_ssl()

import asyncio
import os
os.environ["RESEARCH_FORCE"] = "1"

from app.agents.research.nodes import visuals

async def main():
    state = {"domain": "celonis.com", "company": "Celonis"}
    result = await visuals.run(state)
    data = result.get("visuals")
    if data is None:
        print("No data produced. Errors:", result.get("errors"))
        return
    colors = data.colors if not isinstance(data.colors, dict) else data.colors
    if hasattr(colors, "primary"):
        print("primary:", colors.primary)
        print("secondary:", colors.secondary)
        print("semantic:", colors.semantic)
    else:
        print("primary:", colors.get("primary"))
        print("secondary:", colors.get("secondary"))
        print("semantic:", colors.get("semantic"))

asyncio.run(main())
