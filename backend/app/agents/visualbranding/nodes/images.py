"""backend/app/agents/visualbranding/nodes/images.py

Imagery interpretation node for the Visual Branding agent.

Reads every active competitor's latest scraped marketing images
(research_snapshots, node="visuals") and uses GPT-4o-mini vision to classify
each competitor's representative image across five fixed dimensions (style,
effect, subject, look & feel, color scheme), clusters competitors into
named visual-style archetypes, and computes a pairwise similarity score
between every pair of competitors from their dimension profiles.

Only invoked when `detect_changes_node` (graph.py) found the images
dimension changed since this node's last run.
"""

import json
from datetime import datetime, timezone
from itertools import combinations

import structlog
from openai import AsyncOpenAI

from app.agents.visualbranding.alerts import diff_named_groups
from app.agents.visualbranding.naming import naming_stability_instruction
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
)
from app.agents.visualbranding.state import (
    ArchetypeAnalysis,
    DimensionCategory,
    ImageAnalysis,
    ImageUsage,
    ImagerySimilarity,
    VisualBrandingState,
)
from app.config import get_settings

logger = structlog.get_logger(__name__)

NODE_NAME = "images"

_STYLES = ("Photorealistic", "Illustration", "3D Render", "Abstract")
_EFFECTS = ("Minimalist", "Vibrant", "Moody", "Clean")
_SUBJECTS = ("People", "Product/UI", "Abstract shapes", "Data visualization")
_LOOK_FEELS = ("Corporate", "Playful", "Technical", "Editorial")
_COLOR_SCHEMES = ("Monochrome", "Brand-colored", "Multicolor", "Muted/Pastel")

_DIMENSIONS = (
    ("style", "Style", _STYLES),
    ("effect", "Effect", _EFFECTS),
    ("subject", "Subject", _SUBJECTS),
    ("look_feel", "Look & Feel", _LOOK_FEELS),
    ("color_scheme", "Color Scheme", _COLOR_SCHEMES),
)


# ---------------------------------------------------------------------------
# Source data
# ---------------------------------------------------------------------------

async def _build_image_data() -> tuple[dict[str, list[str]], str]:
    """{domain: [image URLs]} for every active competitor with scraped
    marketing imagery, plus a fingerprint of the raw payload (must match
    graph.py's detect_changes_node exactly)."""
    visuals_by_domain = await get_latest_visuals_by_domain()
    images_dim = extract_dimension(visuals_by_domain, "images")
    fingerprint = compute_fingerprint(images_dim)

    images_by_domain = {
        d: [img["url"] for img in (assets or [])]
        for d, assets in images_dim.items()
        if assets
    }
    return images_by_domain, fingerprint


def _pct(count: int, total: int) -> float:
    return round(count / total * 100, 1) if total else 0.0


# ---------------------------------------------------------------------------
# Vision classification — style / effect / subject / look & feel / color scheme
# ---------------------------------------------------------------------------

async def _classify_images_vision(
    images_by_domain: dict[str, list[str]], openai: AsyncOpenAI
) -> dict[str, dict[str, str]]:
    """{domain: {style, effect, subject, look_feel, color_scheme}} — one
    combined vision call classifying every competitor's representative
    (first scraped) marketing image at once."""
    if not images_by_domain:
        return {}
    domains = list(images_by_domain.keys())
    content: list[dict] = [
        {
            "type": "text",
            "text": (
                "Each image below is one company's representative marketing image, labeled "
                "by index. For each, classify it on five dimensions:\n"
                f"- style: exactly one of {list(_STYLES)}\n"
                f"- effect: exactly one of {list(_EFFECTS)}\n"
                f"- subject: exactly one of {list(_SUBJECTS)}\n"
                f"- look_feel: exactly one of {list(_LOOK_FEELS)}\n"
                f"- color_scheme: exactly one of {list(_COLOR_SCHEMES)}\n\n"
                'Return JSON: {"<index>": {"style": "...", "effect": "...", "subject": "...", '
                '"look_feel": "...", "color_scheme": "..."}, ...} for every index given.'
            ),
        }
    ]
    for i, domain in enumerate(domains):
        urls = images_by_domain[domain]
        # One bad URL (e.g. SVG, which vision can't read) fails this entire
        # combined call for every company in it — prefer a raster variant.
        representative = pick_vision_compatible_url(urls) or urls[0]
        content.append({"type": "text", "text": f"Index {i}: {domain_to_company(domain)}"})
        content.append({"type": "image_url", "image_url": {"url": representative}})

    try:
        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": content}],
            response_format={"type": "json_object"},
        )
        raw = json.loads(response.choices[0].message.content)
        return {domains[int(i)]: v for i, v in raw.items() if i.isdigit() and int(i) < len(domains)}
    except Exception as exc:
        logger.warning("images_vision_classification_failed", error=str(exc))
        return {}


# ---------------------------------------------------------------------------
# Archetype clustering + naming
# ---------------------------------------------------------------------------

def _cluster_archetypes(
    images_by_domain: dict[str, list[str]],
    classifications: dict[str, dict[str, str]],
) -> dict[tuple[str, str], dict]:
    """{(style, effect): {"companies": {...}, "sample_image": str}} — coarse
    clustering on the two most visually distinctive dimensions, mirroring
    fonts.py's (classification, personality) clustering."""
    clusters: dict[tuple[str, str], dict] = {}
    for domain, urls in images_by_domain.items():
        company = domain_to_company(domain)
        info = classifications.get(domain) or {}
        key = (info.get("style", "Photorealistic"), info.get("effect", "Clean"))
        bucket = clusters.setdefault(key, {"companies": set(), "sample_image": urls[0]})
        bucket["companies"].add(company)
    return clusters


async def _name_archetypes(
    clusters: dict[tuple[str, str], dict],
    previous_names: list[str],
    openai: AsyncOpenAI,
) -> dict[tuple[str, str], dict[str, str]]:
    if not clusters:
        return {}
    keys = list(clusters.keys())
    cluster_rows = [
        f'{i}: style="{style}", effect="{effect}", companies={sorted(clusters[(style, effect)]["companies"])}'
        for i, (style, effect) in enumerate(keys)
    ]
    instruction = naming_stability_instruction(previous_names)
    try:
        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Each row below is an imagery-style cluster (style + effect + which "
                        "competitors use it). Give each cluster a short, evocative archetype "
                        'name (2-4 words, e.g. "Clean Product Shots", "Bold Abstract Art") and '
                        "a one-sentence description of what defines the style." + instruction +
                        ' Return JSON: {"<row index>": {"name": "...", "description": "..."}, ...} '
                        "for every row given."
                    ),
                },
                {"role": "user", "content": "\n".join(cluster_rows)},
            ],
            response_format={"type": "json_object"},
        )
        raw = json.loads(response.choices[0].message.content)
        return {key: raw.get(str(i), {}) for i, key in enumerate(keys)}
    except Exception as exc:
        logger.warning("images_archetype_naming_failed", error=str(exc))
        return {
            (style, effect): {"name": f"{effect} {style}", "description": f"{effect} {style.lower()} imagery."}
            for style, effect in keys
        }


# ---------------------------------------------------------------------------
# Similarity — deterministic from the 5-dim profile, no extra LLM call
# ---------------------------------------------------------------------------

def _build_similarity(
    images_by_domain: dict[str, list[str]],
    classifications: dict[str, dict[str, str]],
) -> list[ImagerySimilarity]:
    """Pairwise similarity = fraction of matching dimension values between
    two companies' classified profiles. Only pairs with at least one shared
    dimension are reported — an all-zero pair isn't a meaningful link."""
    dim_keys = [key for key, _, _ in _DIMENSIONS]
    domains = list(images_by_domain.keys())
    results: list[ImagerySimilarity] = []
    for domain_a, domain_b in combinations(domains, 2):
        profile_a = classifications.get(domain_a) or {}
        profile_b = classifications.get(domain_b) or {}
        matches = sum(1 for k in dim_keys if profile_a.get(k) and profile_a.get(k) == profile_b.get(k))
        if matches == 0:
            continue
        results.append(
            ImagerySimilarity(
                company_a=domain_to_company(domain_a),
                company_b=domain_to_company(domain_b),
                similarity=round(matches / len(dim_keys), 2),
            )
        )
    return results


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

async def run(state: VisualBrandingState) -> dict:
    logger.info("visualbranding_images_started")

    images_by_domain, fingerprint = await _build_image_data()
    if not images_by_domain:
        logger.warning("visualbranding_images_skipped", reason="no_source_data")
        return {"errors": ["images: no scraped image data available"]}

    total_companies = len(images_by_domain)
    openai = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)

    classifications = await _classify_images_vision(images_by_domain, openai)

    dimension_categories: dict[str, list[DimensionCategory]] = {}
    for key, _, vocab in _DIMENSIONS:
        buckets: dict[str, set[str]] = {}
        for domain in images_by_domain:
            company = domain_to_company(domain)
            value = (classifications.get(domain) or {}).get(key, vocab[0])
            buckets.setdefault(value, set()).add(company)
        dimension_categories[key] = [
            DimensionCategory(naming=name, percentage=_pct(len(companies), total_companies), companies=sorted(companies))
            for name, companies in buckets.items()
        ]

    previous = get_latest_analysis(NODE_NAME)
    previous_archetype_names = [a.get("naming", "") for a in (previous.get("archetypes") if previous else []) or []]
    clusters = _cluster_archetypes(images_by_domain, classifications)
    named = await _name_archetypes(clusters, previous_archetype_names, openai)
    archetypes = [
        ArchetypeAnalysis(
            naming=named.get(key, {}).get("name", f"{key[1]} {key[0]}"),
            description=named.get(key, {}).get("description", f"{key[1]} {key[0].lower()} imagery."),
            sample_image=cluster["sample_image"],
            companies=sorted(cluster["companies"]),
        )
        for key, cluster in clusters.items()
    ]

    similarity = _build_similarity(images_by_domain, classifications)
    usage = [
        ImageUsage(company=domain_to_company(domain), count=len(urls))
        for domain, urls in images_by_domain.items()
    ]

    analysis = ImageAnalysis(
        archetypes=archetypes,
        similarity=similarity,
        style=dimension_categories["style"],
        effect=dimension_categories["effect"],
        subject=dimension_categories["subject"],
        look_feel=dimension_categories["look_feel"],
        color_scheme=dimension_categories["color_scheme"],
        usage=usage,
    )

    alerts: list[str] = []
    if previous:
        alerts += diff_named_groups("Imagery archetype", previous.get("archetypes"), archetypes)
        alerts += diff_named_groups("Imagery style", previous.get("style"), dimension_categories["style"])
        alerts += diff_named_groups("Imagery effect", previous.get("effect"), dimension_categories["effect"])
        alerts += diff_named_groups("Imagery subject", previous.get("subject"), dimension_categories["subject"])
        alerts += diff_named_groups("Imagery look & feel", previous.get("look_feel"), dimension_categories["look_feel"])
        alerts += diff_named_groups("Imagery color scheme", previous.get("color_scheme"), dimension_categories["color_scheme"])

    run_at = datetime.now(timezone.utc)
    try:
        insert_visualbranding_snapshot(NODE_NAME, run_at, fingerprint, analysis)
        logger.info("visualbranding_images_persisted")
    except Exception as exc:
        logger.error("visualbranding_images_persist_failed", error=str(exc))

    logger.info(
        "visualbranding_images_done",
        competitors=total_companies,
        archetypes=len(archetypes),
        alerts=len(alerts),
    )
    return {"images": analysis, "image_alerts": alerts, "completed_nodes": ["images"]}


if __name__ == "__main__":
    import asyncio
    import truststore

    truststore.inject_into_ssl()  # fixes SSL_CERTIFICATE_VERIFY_FAILED on Windows
    structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

    async def main() -> None:
        result = await run({})
        analysis = result.get("images")
        if analysis is None:
            print("No analysis produced. Errors:", result.get("errors"))
            return
        print(analysis.model_dump_json(indent=2))
        print("Alerts:", result.get("image_alerts"))

    asyncio.run(main())
