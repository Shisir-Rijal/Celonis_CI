"""backend/app/agents/visualbranding/nodes/logos.py

Logo interpretation node for the Visual Branding agent.

Reads every active competitor's latest scraped logo URL (research_snapshots,
node="visuals") and uses GPT-4o-mini vision to actually look at each logo —
unlike colors/fonts, type/color/shape can't be inferred from text metadata
alone, so this node sends the logo images straight to the model.

Placement (where competitors put their logo on marketing imagery) is
classified the same way: the model is shown the company's logo plus a
handful of its scraped marketing images and asked where the logo appears
in each.

Only invoked when `detect_changes_node` (graph.py) found the logo dimension
changed since this node's last run.
"""

import json
from collections import Counter
from datetime import datetime, timezone

import structlog
from openai import AsyncOpenAI

from app.agents.visualbranding.alerts import diff_named_groups
from app.agents.visualbranding.repositories.visualbranding_repository import (
    compute_fingerprint,
    get_latest_analysis,
    insert_visualbranding_snapshot,
)
from app.agents.visualbranding.source_data import (
    domain_to_company,
    extract_dimension,
    get_latest_visuals_by_domain,
    pick_vision_compatible_url,
    pick_vision_compatible_urls,
)
from app.agents.visualbranding.state import (
    DimensionCategory,
    LogoAnalysis,
    LogoPlacement,
    VisualBrandingState,
)
from app.config import get_settings

logger = structlog.get_logger(__name__)

NODE_NAME = "logos"

_TYPES = ("Wordmark", "Combination mark", "Icon-only")
_COLORS = ("Colored", "Monochrome")
_SHAPE_STYLES = ("Rounded", "Angular", "Mixed")
_SIGNAL_SHAPES = ("Circle", "Square", "Abstract", "None")
_POSITIONS = (
    "top-left", "top-center", "top-right", "center",
    "bottom-left", "bottom-center", "bottom-right", "not-present",
)

_MAX_PLACEMENT_SAMPLES = 3  # marketing images checked per company for logo placement


# ---------------------------------------------------------------------------
# Source data
# ---------------------------------------------------------------------------

async def _build_logo_data() -> tuple[dict[str, str], dict[str, list[str]], str]:
    """({domain: primary logo URL}, {domain: [marketing image URLs]}, fingerprint).

    Fingerprint covers only the logo dimension (must match graph.py's
    detect_changes_node exactly) — images are auxiliary input for placement,
    not the dimension this node is gated on.
    """
    visuals_by_domain = await get_latest_visuals_by_domain()
    logo_dim = extract_dimension(visuals_by_domain, "logo")
    fingerprint = compute_fingerprint(logo_dim)

    # Brandfetch often serves SVG as the *first* logo variant; OpenAI vision
    # can't read SVG, and one bad URL fails the entire combined classification
    # call (every company in it, not just this one) — prefer a raster variant
    # when one exists, falling back to urls[0] only if every option is SVG.
    logos_by_domain = {
        d: pick_vision_compatible_url(urls) or urls[0] for d, urls in logo_dim.items() if urls
    }
    images_by_domain = {
        d: pick_vision_compatible_urls(
            [img["url"] for img in (data.get("images") or [])], _MAX_PLACEMENT_SAMPLES
        )
        for d, data in visuals_by_domain.items()
        if d in logos_by_domain
    }
    return logos_by_domain, images_by_domain, fingerprint


def _pct(count: int, total: int) -> float:
    return round(count / total * 100, 1) if total else 0.0


# ---------------------------------------------------------------------------
# Vision classification — logo type / color / shape style / signal shape
# ---------------------------------------------------------------------------

async def _classify_logos_vision(
    logos_by_domain: dict[str, str], openai: AsyncOpenAI
) -> dict[str, dict[str, str]]:
    """{domain: {type, color, shape_style, signal_shape}} — one combined
    vision call classifying every competitor's logo at once."""
    if not logos_by_domain:
        return {}
    domains = list(logos_by_domain.keys())
    content: list[dict] = [
        {
            "type": "text",
            "text": (
                "Each image below is one company's logo, labeled by index. For each, "
                "classify it on four dimensions:\n"
                f'- type: exactly one of {list(_TYPES)} (Wordmark = text only, '
                "Combination mark = text + icon, Icon-only = symbol with no text)\n"
                f"- color: exactly one of {list(_COLORS)}\n"
                f"- shape_style: exactly one of {list(_SHAPE_STYLES)} (overall letterform/icon style)\n"
                f"- signal_shape: exactly one of {list(_SIGNAL_SHAPES)} (the dominant icon "
                'shape if any, or "None" if purely typographic)\n\n'
                'Return JSON: {"<index>": {"type": "...", "color": "...", '
                '"shape_style": "...", "signal_shape": "..."}, ...} for every index given.'
            ),
        }
    ]
    for i, domain in enumerate(domains):
        content.append({"type": "text", "text": f"Index {i}: {domain_to_company(domain)}"})
        content.append({"type": "image_url", "image_url": {"url": logos_by_domain[domain]}})

    try:
        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": content}],
            response_format={"type": "json_object"},
        )
        raw = json.loads(response.choices[0].message.content)
        return {domains[int(i)]: v for i, v in raw.items() if i.isdigit() and int(i) < len(domains)}
    except Exception as exc:
        logger.warning("logos_vision_classification_failed", error=str(exc))
        return {}


async def _classify_placement_vision(
    domain: str, logo_url: str, image_urls: list[str], openai: AsyncOpenAI
) -> str:
    """Show the model the company's logo plus a few of its marketing images;
    ask where (if anywhere) the logo appears in each, then take the majority
    position. Returns "not-present" if no images or no detection."""
    if not image_urls:
        return "not-present"
    content: list[dict] = [
        {
            "type": "text",
            "text": (
                "The first image is this company's logo. The remaining images, labeled by "
                "index, are marketing images scraped from the company's website. For each "
                "labeled image, say where the logo from the first image appears in it: "
                f"exactly one of {list(_POSITIONS)}. Use \"not-present\" if the logo does not "
                'appear at all. Return JSON: {"<index>": "<position>", ...} for every index given.'
            ),
        },
        {"type": "image_url", "image_url": {"url": logo_url}},
    ]
    for i, url in enumerate(image_urls):
        content.append({"type": "text", "text": f"Index {i}:"})
        content.append({"type": "image_url", "image_url": {"url": url}})

    try:
        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": content}],
            response_format={"type": "json_object"},
        )
        raw = json.loads(response.choices[0].message.content)
        positions = [p for p in raw.values() if p in _POSITIONS]
        present = [p for p in positions if p != "not-present"]
        if not present:
            return "not-present"
        return Counter(present).most_common(1)[0][0]
    except Exception as exc:
        logger.warning("logos_placement_failed", domain=domain, error=str(exc))
        return "not-present"


def _buckets_to_categories(buckets: dict[str, set[str]], total: int) -> list[DimensionCategory]:
    return [
        DimensionCategory(naming=name, percentage=_pct(len(companies), total), companies=sorted(companies))
        for name, companies in buckets.items()
    ]


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

async def run(state: VisualBrandingState) -> dict:
    logger.info("visualbranding_logos_started")

    logos_by_domain, images_by_domain, fingerprint = await _build_logo_data()
    if not logos_by_domain:
        logger.warning("visualbranding_logos_skipped", reason="no_source_data")
        return {"errors": ["logos: no scraped logo data available"]}

    total_companies = len(logos_by_domain)
    openai = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)

    classifications = await _classify_logos_vision(logos_by_domain, openai)

    type_buckets: dict[str, set[str]] = {}
    color_buckets: dict[str, set[str]] = {}
    shape_buckets: dict[str, set[str]] = {}
    signal_buckets: dict[str, set[str]] = {}
    for domain in logos_by_domain:
        company = domain_to_company(domain)
        info = classifications.get(domain) or {}
        type_buckets.setdefault(info.get("type", "Wordmark"), set()).add(company)
        color_buckets.setdefault(info.get("color", "Colored"), set()).add(company)
        shape_buckets.setdefault(info.get("shape_style", "Mixed"), set()).add(company)
        signal_buckets.setdefault(info.get("signal_shape", "None"), set()).add(company)

    type_categories = _buckets_to_categories(type_buckets, total_companies)
    color_categories = _buckets_to_categories(color_buckets, total_companies)
    shape_categories = _buckets_to_categories(shape_buckets, total_companies)
    signal_categories = _buckets_to_categories(signal_buckets, total_companies)

    placement_buckets: dict[str, set[str]] = {}
    for domain, logo_url in logos_by_domain.items():
        company = domain_to_company(domain)
        position = await _classify_placement_vision(
            domain, logo_url, images_by_domain.get(domain, []), openai
        )
        placement_buckets.setdefault(position, set()).add(company)
    placement = [
        LogoPlacement(position=pos, percentage=_pct(len(companies), total_companies), companies=sorted(companies))
        for pos, companies in placement_buckets.items()
    ]

    logo_urls = {domain_to_company(d): url for d, url in logos_by_domain.items()}

    analysis = LogoAnalysis(
        type=type_categories,
        color=color_categories,
        shape_style=shape_categories,
        signal_shape=signal_categories,
        placement=placement,
        logo_urls=logo_urls,
    )

    previous = get_latest_analysis(NODE_NAME)
    alerts: list[str] = []
    if previous:
        alerts += diff_named_groups("Logo type", previous.get("type"), type_categories)
        alerts += diff_named_groups("Logo color", previous.get("color"), color_categories)
        alerts += diff_named_groups("Logo shape style", previous.get("shape_style"), shape_categories)
        alerts += diff_named_groups("Logo signal shape", previous.get("signal_shape"), signal_categories)
        alerts += diff_named_groups(
            "Logo placement", previous.get("placement"), placement, name_field="position"
        )

    run_at = datetime.now(timezone.utc)
    try:
        insert_visualbranding_snapshot(NODE_NAME, run_at, fingerprint, analysis)
        logger.info("visualbranding_logos_persisted")
    except Exception as exc:
        logger.error("visualbranding_logos_persist_failed", error=str(exc))

    logger.info("visualbranding_logos_done", competitors=total_companies, alerts=len(alerts))
    return {"logos": analysis, "logo_alerts": alerts, "completed_nodes": ["logos"]}


if __name__ == "__main__":
    import asyncio
    import truststore

    truststore.inject_into_ssl()  # fixes SSL_CERTIFICATE_VERIFY_FAILED on Windows
    structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

    async def main() -> None:
        result = await run({})
        analysis = result.get("logos")
        if analysis is None:
            print("No analysis produced. Errors:", result.get("errors"))
            return
        print(analysis.model_dump_json(indent=2))
        print("Alerts:", result.get("logo_alerts"))

    asyncio.run(main())
