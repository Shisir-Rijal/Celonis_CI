import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import structlog
from app.config import get_settings
import httpx

logger = structlog.get_logger(__name__)

async def _get_brand_data(domain: str) -> dict:
    api_key = get_settings().BRANDFETCH_API_KEY
    if not api_key:
        return {}
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.brandfetch.io/v2/brands/{domain}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
    if response.status_code != 200:
        logger.warning("brandfetch_failed", status=response.status_code, domain=domain)
        return {}
    return response.json()