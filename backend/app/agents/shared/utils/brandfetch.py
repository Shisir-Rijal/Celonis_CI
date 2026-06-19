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
    # Brandfetch's brand-lookup endpoint expects a bare root domain and 400s on
    # a path. Some competitors are tracked at a product-specific path (e.g.
    # "microsoft.com/en-us/microsoft-fabric") because we only care about that
    # sub-brand, not the parent company — falling back to the root domain would
    # return Microsoft's general brand identity, not Fabric's. Skip Brandfetch
    # entirely in that case; the page-scraping fallbacks for logo/colors/fonts
    # already handle path-scoped domains using the sub-brand's own pages.
    if "/" in domain:
        logger.info("brandfetch_skipped_path_domain", domain=domain)
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