"""Quick check of research_snapshots table contents.

Usage (from backend/ directory):
    uv run python scripts/check_snapshots.py
    uv run python scripts/check_snapshots.py uipath.com
    uv run python scripts/check_snapshots.py uipath.com financials
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.supabase_client import get_supabase

db = get_supabase()

args = sys.argv[1:]
company = args[0] if len(args) > 0 else None
node = args[1] if len(args) > 1 else None

query = db.table("research_snapshots").select("company, node, run_at, data")

if company:
    query = query.eq("company", company)
if node:
    query = query.eq("node", node)

rows = query.order("run_at", desc=True).limit(20).execute()

if not rows.data:
    print("Keine Daten gefunden.")
else:
    for r in rows.data:
        print(f"\n{'='*60}")
        print(f"Company : {r['company']}")
        print(f"Node    : {r['node']}")
        print(f"Run at  : {r['run_at']}")
        print(f"Data    :")
        print(json.dumps(r["data"], indent=2))