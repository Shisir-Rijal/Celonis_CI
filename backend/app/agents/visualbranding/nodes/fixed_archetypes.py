"""backend/app/agents/visualbranding/nodes/fixed_archetypes.py

Fixed marketing-archetype classification for the Visual Branding agent.

Companion to nodes/archetypes.py's freely-named clustering: instead of
LLM-invented archetype names that can drift between runs, this node
classifies every company into exactly one of the 12 established Mark &
Pearson brand archetypes (the "Hero and the Outlaw" framework underlying
the 2001 Modern Marketing Model) — Innocent, Sage, Explorer, Outlaw,
Magician, Hero, Lover, Jester, Everyman, Caregiver, Ruler, Creator.

Same source signatures as archetypes.py (color temperature/hue, font
classification/personality, logo type/color, imagery style/effect, video
format), but classification is closed-set: every company always lands in
one of the 12 named buckets, never a brand-new invented name. That gives
stable, recognizable vocabulary for cross-run trend tracking ("3
competitors are 'Hero' this quarter") at the cost of occasionally forcing
a brand into an imperfect fit.

Runs as a fourth fan-in alongside build_alerts/trends/brand_archetypes (see
graph.py) — not gated by detect_changes_node, since it depends on the
combination of every dimension's latest state rather than one raw source
field.
"""

import json
from datetime import datetime, timezone

import structlog
from openai import AsyncOpenAI

from app.agents.visualbranding.nodes.archetypes import _aggregate_signature, _build_signatures
from app.agents.visualbranding.repositories.visualbranding_repository import (
    compute_fingerprint,
    get_latest_analysis,
    insert_visualbranding_snapshot,
)
from app.agents.visualbranding.source_data import (
    domain_to_company,
    get_latest_visuals_by_domain,
    pick_vision_compatible_urls,
)
from app.agents.visualbranding.state import FixedArchetypeAnalysis, FixedBrandArchetype, VisualBrandingState
from app.config import get_settings

logger = structlog.get_logger(__name__)

NODE_NAME = "fixed_archetypes"

# The 12 Mark & Pearson brand archetypes (Modern Marketing Model, 2001) —
# fixed vocabulary, not LLM-invented, so names stay comparable across runs.
FIXED_ARCHETYPE_DEFINITIONS = {
    "Innocent": "Optimistic, simple, pure — light/pastel colors, lots of white space, soft rounded shapes.",
    "Sage": "Knowing, analytical, trustworthy — blue/grey tones, clean sans-serif type, data-driven visuals.",
    "Explorer": "Adventurous, independent — earth tones, nature photography, wide-open imagery.",
    "Outlaw": "Disruptive, rule-breaking — black/red, sharp asymmetric layouts, high-contrast imagery.",
    "Magician": "Visionary, transformative — purple/violet, glow or gradient effects, abstract/futuristic visuals.",
    "Hero": "Bold, high-performing, competitive — strong red/orange, dynamic action imagery, heavy typography.",
    "Lover": "Sensual, intimate, aesthetic — pink/rose/gold, soft lighting, close-up imagery of people.",
    "Jester": "Playful, humorous, unconventional — bright multicolor palettes, illustration over photography.",
    "Everyman": "Down-to-earth, accessible, honest — muted/neutral colors, relatable real-people imagery.",
    "Caregiver": "Nurturing, supportive, warm — warm pastels, people-focused photography, soft rounded shapes.",
    "Ruler": "Authoritative, prestigious — black/gold/navy, symmetric layouts, serif typefaces.",
    "Creator": "Innovative, original — experimental color palettes, illustration/3D mix, unconventional typography.",
}
FIXED_ARCHETYPE_NAMES = tuple(FIXED_ARCHETYPE_DEFINITIONS.keys())

# trait-signature key -> human topic label, only the topics actually present
# in a bucket's aggregate signature get a bullet.
_TRAIT_TOPICS = {
    "color_temp": "Color",
    "color_hue": "Color",
    "font_classification": "Typography",
    "font_personality": "Typography",
    "logo_type": "Logo",
    "logo_color": "Logo",
    "image_style": "Imagery",
    "image_effect": "Imagery",
    "video_format": "Video",
}


# ---------------------------------------------------------------------------
# Classification — closed-set, one combined text-only LLM call
# ---------------------------------------------------------------------------

async def _classify_companies(
    signatures: dict[str, dict[str, str]], openai: AsyncOpenAI
) -> dict[str, str]:
    """{company: one of FIXED_ARCHETYPE_NAMES}."""
    if not signatures:
        return {}
    companies = sorted(signatures.keys())
    definitions = "\n".join(f"- {name}: {desc}" for name, desc in FIXED_ARCHETYPE_DEFINITIONS.items())
    rows = "\n".join(f"{c}: {signatures[c]}" for c in companies)
    try:
        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Classify each company below into exactly one of these 12 brand "
                        f"archetypes, based on its visual identity traits:\n{definitions}\n\n"
                        "Each company's traits (color temperature/hue, font classification/"
                        "personality, logo type/color, imagery style/effect, video format) are "
                        "given as a dict — not every trait is present for every company.\n\n"
                        'Return JSON: {"<company>": "<one of the 12 archetype names exactly as '
                        'given>", ...} for every company listed.'
                    ),
                },
                {"role": "user", "content": rows},
            ],
            response_format={"type": "json_object"},
        )
        raw = json.loads(response.choices[0].message.content)
        return {c: raw[c] for c in companies if raw.get(c) in FIXED_ARCHETYPE_NAMES}
    except Exception as exc:
        logger.warning("fixed_archetypes_classification_failed", error=str(exc))
        return {}


# ---------------------------------------------------------------------------
# Trait bullets — one combined call across every occupied archetype
# ---------------------------------------------------------------------------

async def _describe_archetypes(
    buckets: dict[str, set[str]],
    signatures: dict[str, dict[str, str]],
    openai: AsyncOpenAI,
) -> dict[str, dict]:
    """{archetype name -> {"keywords", "vibe", "traits": [{"topic", "description"}, ...]}}."""
    if not buckets:
        return {}
    names = list(buckets.keys())
    rows = []
    for name in names:
        aggregate = _aggregate_signature(buckets[name], signatures)
        topics = sorted({_TRAIT_TOPICS[k] for k in aggregate if k in _TRAIT_TOPICS})
        rows.append(
            f"{name}: definition={FIXED_ARCHETYPE_DEFINITIONS[name]}, "
            f"observed_traits={aggregate}, topics_to_cover={topics}, "
            f"companies={sorted(buckets[name])}"
        )
    try:
        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Each row below is one brand archetype, the companies currently "
                        "classified into it, and their aggregate observed visual traits. Write, "
                        "for each: 3-5 single-word keywords capturing its vibe, a one-sentence "
                        "overall vibe summary, and one short bullet-point sentence per topic "
                        "listed in topics_to_cover describing how that archetype actually "
                        "manifests for THESE companies (not a generic textbook definition) — "
                        "skip any topic not listed.\n\n"
                        'Return JSON: {"<archetype name>": {"keywords": ["...", ...], "vibe": '
                        '"...", "traits": [{"topic": "...", "description": "..."}, ...]}, ...} '
                        "for every archetype given."
                    ),
                },
                {"role": "user", "content": "\n".join(rows)},
            ],
            response_format={"type": "json_object"},
        )
        raw = json.loads(response.choices[0].message.content)
        return {name: raw.get(name, {}) for name in names}
    except Exception as exc:
        logger.warning("fixed_archetypes_description_failed", error=str(exc))
        return {
            name: {"keywords": [], "vibe": FIXED_ARCHETYPE_DEFINITIONS[name], "traits": []}
            for name in names
        }


# ---------------------------------------------------------------------------
# Best-fit representative image — vision call across candidate images
# ---------------------------------------------------------------------------

async def _pick_best_image(
    archetype_name: str,
    companies: set[str],
    visuals_by_domain: dict[str, dict],
    openai: AsyncOpenAI,
) -> str | None:
    """Asks vision to pick whichever already-scraped image (across every
    company in this bucket) best matches the archetype's definition — a
    closer fit than just grabbing the first company's first image."""
    candidates: list[str] = []
    for domain, data in visuals_by_domain.items():
        if domain_to_company(domain) not in companies:
            continue
        urls = [img.get("url") for img in (data.get("images") or []) if img.get("url")]
        candidates += pick_vision_compatible_urls(urls, 2)
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    candidates = candidates[:12]  # cap combined-call size
    definition = FIXED_ARCHETYPE_DEFINITIONS[archetype_name]
    content: list[dict] = [
        {
            "type": "text",
            "text": (
                f'Pick the single image below that best visually represents the "{archetype_name}" '
                f"brand archetype: {definition}\n\n"
                'Return JSON: {"index": <number>} for the best-matching image, 0-indexed.'
            ),
        }
    ]
    for i, url in enumerate(candidates):
        content.append({"type": "text", "text": f"Index {i}"})
        content.append({"type": "image_url", "image_url": {"url": url}})

    try:
        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": content}],
            response_format={"type": "json_object"},
        )
        raw = json.loads(response.choices[0].message.content)
        idx = int(raw.get("index", 0))
        return candidates[idx] if 0 <= idx < len(candidates) else candidates[0]
    except Exception as exc:
        logger.warning("fixed_archetypes_image_pick_failed", archetype=archetype_name, error=str(exc))
        return candidates[0]


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

async def run(state: VisualBrandingState) -> dict:
    logger.info("visualbranding_fixed_archetypes_started")

    colors = get_latest_analysis("colors")
    fonts = get_latest_analysis("fonts")
    logos = get_latest_analysis("logos")
    images = get_latest_analysis("images")
    videos = get_latest_analysis("videos")

    signatures = _build_signatures(colors, fonts, logos, images, videos)
    if not signatures:
        logger.info("visualbranding_fixed_archetypes_skipped", reason="no_dimension_analyses_yet")
        return {}

    openai = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)
    assignments = await _classify_companies(signatures, openai)

    buckets: dict[str, set[str]] = {}
    for company, name in assignments.items():
        buckets.setdefault(name, set()).add(company)

    descriptions = await _describe_archetypes(buckets, signatures, openai)
    visuals_by_domain = await get_latest_visuals_by_domain()

    archetypes: list[FixedBrandArchetype] = []
    for name, companies in buckets.items():
        info = descriptions.get(name, {})
        sample_image = await _pick_best_image(name, companies, visuals_by_domain, openai)
        archetypes.append(
            FixedBrandArchetype(
                naming=name,
                keywords=info.get("keywords", []),
                vibe=info.get("vibe", FIXED_ARCHETYPE_DEFINITIONS[name]),
                traits=info.get("traits", []),
                sample_image=sample_image,
                companies=sorted(companies),
            )
        )
    # Stable, recognizable order — not whatever order the LLM classified in.
    archetypes.sort(key=lambda a: FIXED_ARCHETYPE_NAMES.index(a.naming))

    analysis = FixedArchetypeAnalysis(archetypes=archetypes)

    run_at = datetime.now(timezone.utc)
    try:
        fingerprint = compute_fingerprint(signatures)
        insert_visualbranding_snapshot(NODE_NAME, run_at, fingerprint, analysis)
        logger.info("visualbranding_fixed_archetypes_persisted")
    except Exception as exc:
        logger.error("visualbranding_fixed_archetypes_persist_failed", error=str(exc))

    logger.info(
        "visualbranding_fixed_archetypes_done",
        archetypes=len(archetypes),
        companies_classified=len(assignments),
    )
    return {"fixed_archetypes": analysis, "completed_nodes": ["fixed_archetypes"]}


if __name__ == "__main__":
    import asyncio
    import truststore

    truststore.inject_into_ssl()  # fixes SSL_CERTIFICATE_VERIFY_FAILED on Windows
    structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

    async def main() -> None:
        result = await run({})
        analysis = result.get("fixed_archetypes")
        if analysis is None:
            print("No analysis produced (no dimension analyses persisted yet).")
            return
        print(analysis.model_dump_json(indent=2))

    asyncio.run(main())
