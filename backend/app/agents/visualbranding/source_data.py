"""backend/app/agents/visualbranding/source_data.py

Shared helpers for pulling the raw, per-competitor scraped visuals data
(research_snapshots, node="visuals") that every visualbranding node
interprets. Centralized here so the change-detection router (graph.py)
and the nodes themselves (colors.py, ...) fetch/fingerprint the exact same
data — if they diverged, the router could decide a dimension's input
changed using a different shape than what the node actually analyzes,
silently skipping runs it shouldn't (or running ones it doesn't need to).
"""

from app.agents.research.repositories.research_repository import get_latest_snapshot
from app.agents.shared.competitors import get_competitor_names

VISUALS_NODE = "visuals"

# Populated by get_latest_visuals_by_domain() (called once at the start of
# every node's run()) so the later, plain-sync domain_to_company() calls
# throughout that same run can look up the real name instead of guessing.
_company_names: dict[str, str] = {}


async def get_latest_visuals_by_domain() -> dict[str, dict]:
    """{domain: latest VisualsData payload} for every active competitor (+ Celonis)."""
    global _company_names
    _company_names = await get_competitor_names()
    result: dict[str, dict] = {}
    for domain in _company_names:
        snapshot = get_latest_snapshot(domain, VISUALS_NODE)
        if snapshot:
            result[domain] = snapshot
    return result


def extract_dimension(visuals_by_domain: dict[str, dict], dimension: str) -> dict[str, object]:
    """{domain: that dimension's raw value}, e.g. dimension="colors" ->
    {domain: {"primary": [...], "secondary": [...]}}. Domains missing that
    dimension entirely are dropped rather than included as None, so a
    competitor with no scraped videos yet doesn't constantly look "changed"."""
    return {
        domain: data.get(dimension)
        for domain, data in visuals_by_domain.items()
        if data.get(dimension) is not None
    }


def domain_to_company(domain: str) -> str:
    """e.g. "ibm.com" -> "IBM", "uipath.com" -> "UiPath" — the real display
    name from the competitors table (populated by get_latest_visuals_by_domain,
    which every node calls first). Falls back to a naive
    domain.split(".")[0].capitalize() guess only if the domain isn't in that
    cache (e.g. called before any node has fetched it, or in a test)."""
    return _company_names.get(domain) or domain.split(".")[0].capitalize()


# OpenAI's vision input only accepts these raster formats — notably not SVG,
# which Brandfetch serves as the *first* logo variant for many domains.
_VISION_COMPATIBLE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def _url_extension(url: str) -> str:
    path = url.split("?", 1)[0].rsplit("/", 1)[-1]
    return path.rsplit(".", 1)[-1].lower() if "." in path else ""


def pick_vision_compatible_url(urls: list[str]) -> str | None:
    """First URL in raster format, or None if every option is unsupported
    (e.g. SVG-only). Logos/images nodes use this instead of blindly taking
    urls[0] — a single SVG slipped into a combined vision call fails the
    *entire* batch (every company in that call), not just the bad one."""
    for url in urls:
        if _url_extension(url) in _VISION_COMPATIBLE_EXTENSIONS:
            return url
    return None


def pick_vision_compatible_urls(urls: list[str], limit: int) -> list[str]:
    """Up to `limit` raster-format URLs, in original order."""
    compatible = [u for u in urls if _url_extension(u) in _VISION_COMPATIBLE_EXTENSIONS]
    return compatible[:limit]
