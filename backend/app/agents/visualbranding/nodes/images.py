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

import asyncio
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
    pick_vision_compatible_urls,
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

# "Gradient" called out separately from "Abstract" — a smooth multi-color
# gradient/blob background (OpenAI's signature look) is a distinct, very
# recognizable style choice, not just a generic "Abstract" composition.
_STYLES = ("Photorealistic", "Illustration", "3D Render", "Gradient", "Abstract")
_EFFECTS = ("Minimalist", "Vibrant", "Moody", "Clean")
# Beyond generic content type, several competitors' imagery is defined by
# *which industry/setting* it depicts (e.g. Palantir's military/defense
# scenes) — a generic "People" bucket erases that distinction entirely, even
# though it's one of the more telling brand signals in the set. The vocab
# below keeps the original non-figurative buckets (Product/UI, Abstract
# shapes, Data visualization) but replaces the single catch-all "People" with
# specific depicted contexts. "Mascot/Character" is its own bucket too — a
# branded illustrated character (e.g. UiPath's robot mascot) was previously
# forced into "Abstract shapes" for lack of anywhere else to go, which made
# its actual classification look wrong even though the model had no better
# option to pick from.
_SUBJECTS = (
    "Product/UI", "Abstract shapes", "Data visualization", "Mascot/Character",
    "Office/Corporate", "Military/Defense", "Government/Public sector",
    "Industrial/Manufacturing", "Healthcare/Medical", "Finance/Trading",
    "Logistics/Supply chain", "Retail/Consumer", "Technology/Engineering",
)
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

_SAMPLE_IMAGES_PER_DOMAIN = 4


def _classification_prompt(count: int) -> str:
    return (
        f"Below are {count} representative marketing images from one company — they may mix "
        "photos and illustrations. Looking at all of them together, classify the company's "
        "overall predominant imagery style across five dimensions:\n"
        f"- style: exactly one of {list(_STYLES)} — use \"Gradient\" for smooth multi-color "
        'gradient/blob backgrounds, not "Abstract"\n'
        f"- effect: exactly one of {list(_EFFECTS)}\n"
        f"- subject: exactly one of {list(_SUBJECTS)} — pick the most specific one that matches "
        "what is actually depicted (e.g. soldiers, weapons, or command centers -> "
        '"Military/Defense", not a generic people category; office workers in a meeting -> '
        '"Office/Corporate"; a branded illustrated character/mascot -> "Mascot/Character", not '
        '"Abstract shapes"; only use "Product/UI"/"Abstract shapes"/"Data visualization" when no '
        "real-world setting, person, or character is shown at all\n"
        f"- look_feel: exactly one of {list(_LOOK_FEELS)}\n"
        f"- color_scheme: exactly one of {list(_COLOR_SCHEMES)}\n\n"
        'Return JSON: {"style": "...", "effect": "...", "subject": "...", '
        '"look_feel": "...", "color_scheme": "..."}.'
    )


async def _ask_vision(urls: list[str], openai: AsyncOpenAI) -> dict[str, str]:
    content: list[dict] = [{"type": "text", "text": _classification_prompt(len(urls))}]
    for url in urls:
        content.append({"type": "image_url", "image_url": {"url": url}})
    response = await openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": content}],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


def _sample_urls(urls: list[str]) -> list[str]:
    """Up to _SAMPLE_IMAGES_PER_DOMAIN images — the same picking logic used
    for vision classification below is also reused to build the frontend's
    per-company preview thumbnails, so what's shown in the UI is always
    grounded in what the model actually looked at when assigning a category.
    A single cherry-picked "representative" image can easily not support the
    verdict at all (e.g. showing only a company's one mascot image under an
    "Abstract shapes" bucket the model assigned based on its other, genuinely
    abstract images) — showing the whole sample set lets the user judge the
    classification's basis for themselves instead of just the worst case."""
    sample_urls = pick_vision_compatible_urls(urls, _SAMPLE_IMAGES_PER_DOMAIN)
    if sample_urls:
        return sample_urls
    single = pick_vision_compatible_url(urls)
    return [single] if single else []


async def _classify_domain_vision(
    domain: str, urls: list[str], openai: AsyncOpenAI
) -> dict[str, str] | None:
    """One company's classification from up to _SAMPLE_IMAGES_PER_DOMAIN of its
    images (so a company that mixes photos and illustrations gets a holistic
    verdict, not just whatever its single first-scraped image happens to be).
    Isolated per company — a bad/timed-out image URL only drops that one
    company's classification instead of failing every competitor's at once,
    which previously collapsed everyone into the same default archetype."""
    sample_urls = _sample_urls(urls)
    if not sample_urls:
        return None

    try:
        return await _ask_vision(sample_urls, openai)
    except Exception as exc:
        logger.warning(
            "images_vision_classification_failed", domain=domain, error=str(exc), images=len(sample_urls)
        )
        if len(sample_urls) == 1:
            return None
        try:
            return await _ask_vision(sample_urls[:1], openai)
        except Exception as exc2:
            logger.warning("images_vision_classification_failed", domain=domain, error=str(exc2), images=1)
            return None


async def _classify_images_vision(
    images_by_domain: dict[str, list[str]], openai: AsyncOpenAI
) -> dict[str, dict[str, str]]:
    """{domain: {style, effect, subject, look_feel, color_scheme}} — one
    isolated vision call per company, run concurrently, each looking at
    several of that company's images."""
    if not images_by_domain:
        return {}
    domains = list(images_by_domain.keys())
    results = await asyncio.gather(
        *[_classify_domain_vision(d, images_by_domain[d], openai) for d in domains]
    )
    return {d: r for d, r in zip(domains, results) if r}


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
    dimension are reported — an all-zero pair isn't a meaningful link. Each
    match also records *which* dimension(s) matched and on what value (the
    "why"), plus a few sample images from each side so the frontend can show
    an actual side-by-side, not just a percentage."""
    domains = list(images_by_domain.keys())
    sample_images = {
        d: pick_vision_compatible_urls(urls, _SAMPLE_IMAGES_PER_DOMAIN) or urls[:_SAMPLE_IMAGES_PER_DOMAIN]
        for d, urls in images_by_domain.items()
    }
    results: list[ImagerySimilarity] = []
    for domain_a, domain_b in combinations(domains, 2):
        profile_a = classifications.get(domain_a) or {}
        profile_b = classifications.get(domain_b) or {}
        shared_traits = [
            {"dimension": label, "value": profile_a[key]}
            for key, label, _ in _DIMENSIONS
            if profile_a.get(key) and profile_a.get(key) == profile_b.get(key)
        ]
        if not shared_traits:
            continue
        results.append(
            ImagerySimilarity(
                company_a=domain_to_company(domain_a),
                company_b=domain_to_company(domain_b),
                similarity=round(len(shared_traits) / len(_DIMENSIONS), 2),
                shared_traits=shared_traits,
                sample_images_a=sample_images.get(domain_a, []),
                sample_images_b=sample_images.get(domain_b, []),
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
    image_samples = {
        domain_to_company(domain): _sample_urls(urls)
        for domain, urls in images_by_domain.items()
    }

    analysis = ImageAnalysis(
        archetypes=archetypes,
        similarity=similarity,
        style=dimension_categories["style"],
        effect=dimension_categories["effect"],
        subject=dimension_categories["subject"],
        look_feel=dimension_categories["look_feel"],
        color_scheme=dimension_categories["color_scheme"],
        usage=usage,
        image_samples=image_samples,
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
