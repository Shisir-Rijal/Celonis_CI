"""One-off script: run only the visuals research node for a given domain.

Usage: uv run python scripts/scrape_visuals.py ibm.com
"""
import asyncio
import sys

import structlog
import truststore

truststore.inject_into_ssl()

from app.agents.research.nodes.visuals import run

structlog.configure(processors=[structlog.dev.ConsoleRenderer()])


async def main():
    domain = sys.argv[1] if len(sys.argv) > 1 else "celonis.com"
    state = {"competitor_domain": domain}
    result = await run(state)
    if result.get("errors"):
        print("Errors:", result["errors"])
    else:
        print(result["visuals"].model_dump_json(indent=2))


asyncio.run(main())
