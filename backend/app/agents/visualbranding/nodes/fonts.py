"""backend/app/agents/visualbranding/nodes/fonts.py

Font interpretation node for the Visual Branding agent.

Reads every active competitor's latest scraped fonts (research_snapshots,
node="visuals"), classifies them, and produces the cross-competitor
FontAnalysis that backs the branding page's Fonts Comparison section
(shared-font groups, style/weight/personality breakdowns, archetypes).

Only invoked when `detect_changes_node` (graph.py) found the fonts
dimension changed since this node's last run.
"""

import json
from datetime import datetime, timezone

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
)
from app.agents.visualbranding.state import (
    DimensionCategory,
    FontAnalysis,
    FontArchetype,
    SimilarFontGroup,
    VisualBrandingState,
)
from app.config import get_settings

logger = structlog.get_logger(__name__)

NODE_NAME = "fonts"

_CLASSIFICATIONS = ("Serif", "Sans-serif", "Monospace", "Display")
_PERSONALITIES = ("Modern", "Traditional", "Playful", "Technical")


# ---------------------------------------------------------------------------
# Source data
# ---------------------------------------------------------------------------

async def _build_font_data() -> tuple[dict[str, list[dict]], str]:
    """{domain: [FontInfo dict, ...]} for every active competitor with scraped
    fonts, plus a fingerprint of that exact payload for change-detection."""
    visuals_by_domain = await get_latest_visuals_by_domain()
    fonts_by_domain = extract_dimension(visuals_by_domain, "fonts")
    # Fingerprint the raw extract_dimension result — must match exactly what
    # graph.py's detect_changes_node hashes, or the router and this node's
    # persisted fingerprint can never agree on "changed".
    fingerprint = compute_fingerprint(fonts_by_domain)
    fonts_by_domain = {d: f for d, f in fonts_by_domain.items() if f}
    return fonts_by_domain, fingerprint


# ---------------------------------------------------------------------------
# Pure helpers — weight bucketing
# ---------------------------------------------------------------------------

def _weight_bucket(weight: str) -> str | None:
    try:
        w = int(weight)
    except (TypeError, ValueError):
        return None
    if w < 400:
        return "Light"
    if w <= 500:
        return "Regular"
    return "Bold-heavy"


def _classify_weight_emphasis(fonts_by_domain: dict[str, list[dict]]) -> dict[str, set[str]]:
    """{bucket: {companies}} — each company's dominant weight bucket across
    every weight value scraped for any of its fonts."""
    buckets: dict[str, set[str]] = {}
    for domain, fonts in fonts_by_domain.items():
        company = domain_to_company(domain)
        counts: dict[str, int] = {}
        for font in fonts:
            for w in font.get("weights") or []:
                bucket = _weight_bucket(w)
                if bucket:
                    counts[bucket] = counts.get(bucket, 0) + 1
        if not counts:
            continue
        dominant = max(counts.items(), key=lambda kv: kv[1])[0]
        buckets.setdefault(dominant, set()).add(company)
    return buckets


def _build_similar_fonts(fonts_by_domain: dict[str, list[dict]]) -> dict[str, set[str]]:
    """{font_family_name: {companies using it}} — only families used by 2+
    competitors are an actual "similarity" worth reporting."""
    by_family: dict[str, set[str]] = {}
    for domain, fonts in fonts_by_domain.items():
        company = domain_to_company(domain)
        for font in fonts:
            name = font.get("name")
            if name:
                by_family.setdefault(name, set()).add(company)
    return {name: companies for name, companies in by_family.items() if len(companies) >= 2}


def _pct(count: int, total: int) -> float:
    return round(count / total * 100, 1) if total else 0.0


# ---------------------------------------------------------------------------
# LLM interpretation
# ---------------------------------------------------------------------------

async def _classify_fonts(font_names: list[str], openai: AsyncOpenAI) -> dict[str, dict[str, str]]:
    """One combined call: {font name -> {classification, personality}}."""
    if not font_names:
        return {}
    try:
        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "For each font name below, classify its typeface style and personality. "
                        f'classification must be exactly one of: {", ".join(_CLASSIFICATIONS)}. '
                        f'personality must be exactly one of: {", ".join(_PERSONALITIES)}. '
                        'Return JSON: {"<font name>": {"classification": "...", "personality": "..."}, '
                        '...} for every font name given.'
                    ),
                },
                {"role": "user", "content": "\n".join(font_names)},
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as exc:
        logger.warning("fonts_classification_failed", error=str(exc))
        return {name: {"classification": "Sans-serif", "personality": "Modern"} for name in font_names}


async def _describe_similar_fonts(
    groups: dict[str, set[str]], openai: AsyncOpenAI
) -> dict[str, str]:
    if not groups:
        return {}
    prompt_rows = [f'"{name}": companies={sorted(companies)}' for name, companies in groups.items()]
    try:
        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "For each shared font family below, write one short sentence (max 20 "
                        "words) describing its style and why competitors might favor it. Return "
                        'JSON: {"<font name>": "<sentence>", ...} for every name given.'
                    ),
                },
                {"role": "user", "content": "\n".join(prompt_rows)},
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as exc:
        logger.warning("fonts_similar_description_failed", error=str(exc))
        return {
            name: f"Shared by {len(companies)} tracked competitor(s)."
            for name, companies in groups.items()
        }


def _cluster_archetypes(
    fonts_by_domain: dict[str, list[dict]],
    classifications: dict[str, dict[str, str]],
) -> dict[tuple[str, str], dict[str, set[str] | str]]:
    """{(classification, personality): {"companies": {...}, "sample_font_name": str}} —
    each company's *first* scraped font stands in as its representative font."""
    clusters: dict[tuple[str, str], dict] = {}
    for domain, fonts in fonts_by_domain.items():
        if not fonts:
            continue
        company = domain_to_company(domain)
        primary_name = fonts[0].get("name")
        info = classifications.get(primary_name) or {}
        key = (info.get("classification", "Sans-serif"), info.get("personality", "Modern"))
        bucket = clusters.setdefault(key, {"companies": set(), "sample_font_name": primary_name})
        bucket["companies"].add(company)
    return clusters


async def _name_archetypes(
    clusters: dict[tuple[str, str], dict],
    previous_names: list[str],
    openai: AsyncOpenAI,
) -> dict[tuple[str, str], dict[str, str]]:
    """{cluster key -> {"name": ..., "description": ...}}."""
    if not clusters:
        return {}
    keys = list(clusters.keys())
    cluster_rows = [
        f'{i}: classification="{cls}", personality="{pers}", '
        f'companies={sorted(clusters[(cls, pers)]["companies"])}'
        for i, (cls, pers) in enumerate(keys)
    ]
    instruction = naming_stability_instruction(previous_names)
    try:
        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Each row below is a font-style cluster (classification + personality + "
                        "which competitors use it). Give each cluster a short, evocative archetype "
                        'name (2-4 words, e.g. "Geometric Sans", "Technical Mono", "Editorial '
                        'Serif") and a one-sentence description of what defines the style.' + instruction +
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
        logger.warning("fonts_archetype_naming_failed", error=str(exc))
        return {
            (cls, pers): {"name": f"{pers} {cls}", "description": f"{pers} {cls.lower()} typeface."}
            for cls, pers in keys
        }


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

async def run(state: VisualBrandingState) -> dict:
    logger.info("visualbranding_fonts_started")

    fonts_by_domain, fingerprint = await _build_font_data()
    if not fonts_by_domain:
        logger.warning("visualbranding_fonts_skipped", reason="no_source_data")
        return {"errors": ["fonts: no scraped font data available"]}

    total_companies = len(fonts_by_domain)
    distinct_names = sorted({
        font.get("name") for fonts in fonts_by_domain.values() for font in fonts if font.get("name")
    })

    openai = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)
    classifications = await _classify_fonts(distinct_names, openai)

    # --- classification / personality (fixed buckets, deterministic assignment) ---
    classification_buckets: dict[str, set[str]] = {}
    personality_buckets: dict[str, set[str]] = {}
    for domain, fonts in fonts_by_domain.items():
        if not fonts:
            continue
        company = domain_to_company(domain)
        info = classifications.get(fonts[0].get("name")) or {}
        classification_buckets.setdefault(info.get("classification", "Sans-serif"), set()).add(company)
        personality_buckets.setdefault(info.get("personality", "Modern"), set()).add(company)

    classification = [
        DimensionCategory(naming=name, percentage=_pct(len(companies), total_companies), companies=sorted(companies))
        for name, companies in classification_buckets.items()
    ]
    personality = [
        DimensionCategory(naming=name, percentage=_pct(len(companies), total_companies), companies=sorted(companies))
        for name, companies in personality_buckets.items()
    ]

    # --- weight emphasis (deterministic from scraped weights) ---
    weight_buckets = _classify_weight_emphasis(fonts_by_domain)
    weight_emphasis = [
        DimensionCategory(naming=name, percentage=_pct(len(companies), total_companies), companies=sorted(companies))
        for name, companies in weight_buckets.items()
    ]

    # --- similar fonts (deterministic grouping by exact shared family) ---
    similar_groups = _build_similar_fonts(fonts_by_domain)
    similar_descriptions = await _describe_similar_fonts(similar_groups, openai)
    similar_fonts = [
        SimilarFontGroup(
            companies=sorted(companies),
            shared_font_family=name,
            sample_font_name=name,
            note=similar_descriptions.get(name),
        )
        for name, companies in similar_groups.items()
    ]

    # --- archetypes (LLM-clustered + naming-stable) ---
    previous = get_latest_analysis(NODE_NAME)
    previous_archetype_names = [a.get("naming", "") for a in (previous.get("archetypes") if previous else []) or []]
    clusters = _cluster_archetypes(fonts_by_domain, classifications)
    named = await _name_archetypes(clusters, previous_archetype_names, openai)
    archetypes = [
        FontArchetype(
            naming=named.get(key, {}).get("name", f"{key[1]} {key[0]}"),
            description=named.get(key, {}).get("description", f"{key[1]} {key[0].lower()} typeface."),
            sample_font_name=cluster["sample_font_name"],
            companies=sorted(cluster["companies"]),
        )
        for key, cluster in clusters.items()
    ]

    analysis = FontAnalysis(
        similar_fonts=similar_fonts,
        archetypes=archetypes,
        classification=classification,
        weight_emphasis=weight_emphasis,
        personality=personality,
    )

    # --- alerts: only previously-empty-or-different content gets flagged ---
    alerts: list[str] = []
    if previous:
        alerts += diff_named_groups("Font classification", previous.get("classification"), classification)
        alerts += diff_named_groups("Font weight emphasis", previous.get("weight_emphasis"), weight_emphasis)
        alerts += diff_named_groups("Font personality", previous.get("personality"), personality)
        alerts += diff_named_groups("Font archetype", previous.get("archetypes"), archetypes)

    run_at = datetime.now(timezone.utc)
    try:
        insert_visualbranding_snapshot(NODE_NAME, run_at, fingerprint, analysis)
        logger.info("visualbranding_fonts_persisted")
    except Exception as exc:
        logger.error("visualbranding_fonts_persist_failed", error=str(exc))

    logger.info(
        "visualbranding_fonts_done",
        competitors=total_companies,
        archetypes=len(archetypes),
        alerts=len(alerts),
    )
    return {"fonts": analysis, "font_alerts": alerts, "completed_nodes": ["fonts"]}


if __name__ == "__main__":
    import asyncio
    import truststore

    truststore.inject_into_ssl()  # fixes SSL_CERTIFICATE_VERIFY_FAILED on Windows
    structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

    async def main() -> None:
        result = await run({})
        analysis = result.get("fonts")
        if analysis is None:
            print("No analysis produced. Errors:", result.get("errors"))
            return
        print(analysis.model_dump_json(indent=2))
        print("Alerts:", result.get("font_alerts"))

    asyncio.run(main())
