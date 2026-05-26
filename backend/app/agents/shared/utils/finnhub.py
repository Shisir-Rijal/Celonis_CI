import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import httpx
from app.config import get_settings

def _get_symbol(domain: str) -> str | None:
    company_name = domain.replace(".com", "").replace(".io", "")
    response = httpx.get(
        "https://finnhub.io/api/v1/search",
        params={"q": company_name, "token": get_settings().FINNHUB_API_KEY},
        timeout=10,
    )
    results = response.json().get("result", [])
    for r in results:
        if r.get("type") == "Common Stock":
            return r["symbol"]
    return None
