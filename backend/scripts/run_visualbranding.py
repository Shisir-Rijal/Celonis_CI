"""backend/scripts/run_visualbranding.py

Manueller Runner für den Visual Branding Interpretation Graph.
Liest die zuletzt gescrapten research_snapshots (visuals-node) für alle
aktiven Competitors und interpretiert sie (colors/fonts/logos/images/videos +
alerts/trends/archetypes), sofern sich die jeweilige Dimension seit dem
letzten Lauf geändert hat.

Verwendung:
    PYTHONPATH=. uv run python scripts/run_visualbranding.py
"""

import asyncio
import sys

import structlog
import truststore

truststore.inject_into_ssl()

structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

from app.agents.visualbranding.graph import visualbranding_graph


async def main() -> None:
    result = await visualbranding_graph.ainvoke({})
    print("\nDimensions in final state:", [k for k in result if k in ("colors", "fonts", "logos", "images", "videos")])


if __name__ == "__main__":
    asyncio.run(main())
