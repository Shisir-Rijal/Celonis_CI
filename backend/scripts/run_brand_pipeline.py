"""backend/scripts/run_brand_pipeline.py

Manueller Runner für die Brand Intelligence Pipeline.

Verwendung:
    python scripts/run_brand_pipeline.py --competitor sap.com
    python scripts/run_brand_pipeline.py --competitor sap.com --nodes seogeo
    python scripts/run_brand_pipeline.py --competitor ibm.com --nodes seogeo news

Issue #86: Brand Intelligence Pipeline — LangGraph foundation and manual runner
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Damit Python app.* Imports findet wenn das Script direkt aufgerufen wird
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.brand.graph import brand_graph


async def main(competitor_domain: str, nodes_to_run: list[str]) -> None:
    """Baut den initialen State und ruft den Brand Graph auf."""

    # Initialer State — alle Felder die BrandPipelineState erwartet
    initial_state = {
        "competitor_domain": competitor_domain,
        "nodes_to_run": nodes_to_run,   # leer = alle Research Nodes
        "profile": None,
        "results": {},
        "errors": [],
        "completed_capabilities": [],
    }

    print(f"\nStarte Brand Pipeline für: {competitor_domain}")
    if nodes_to_run:
        print(f"Research Nodes: {', '.join(nodes_to_run)}")
    else:
        print("Research Nodes: alle")
    print("-" * 40)

    # Graph aufrufen — gibt den finalen State zurück
    result = await brand_graph.ainvoke(initial_state)

    # Ergebnis ausgeben
    print("\nAbgeschlossen:")
    print(f"  Capabilities: {result['completed_capabilities']}")

    if result["errors"]:
        print(f"\nFehler:")
        for error in result["errors"]:
            print(f"  {error}")
    else:
        print("  Keine Fehler")


if __name__ == "__main__":
    # Argumente definieren
    parser = argparse.ArgumentParser(
        description="Brand Intelligence Pipeline manuell starten"
    )
    parser.add_argument(
        "--competitor",
        required=True,
        help="Domain des Competitors, z.B. sap.com",
    )
    parser.add_argument(
        "--nodes",
        nargs="*",                  # 0 oder mehr Werte: --nodes seogeo news
        default=[],
        help="Research Nodes die geladen werden sollen (leer = alle)",
    )

    args = parser.parse_args()

    # Async main starten
    asyncio.run(main(
        competitor_domain=args.competitor,
        nodes_to_run=args.nodes,
    ))
