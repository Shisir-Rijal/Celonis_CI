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
import re
import urllib.parse
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
    FontUsage,
    SimilarFontGroup,
    VisualBrandingState,
)
from app.config import get_settings

logger = structlog.get_logger(__name__)

NODE_NAME = "fonts"

_CLASSIFICATIONS = ("Serif", "Sans-serif", "Monospace", "Display")
_PERSONALITIES = ("Modern", "Traditional", "Playful", "Technical")

# Trailing script/language qualifiers that font foundries (IBM Plex, Noto, ...)
# append to a family name to denote a script-specific variant of the *same*
# typeface — e.g. "IBM Plex Sans Arabic" is not a different font from
# "IBM Plex Sans", just its Arabic-script companion. Stripped so similarity
# grouping and the distinct-font-count below treat them as one family.
_SCRIPT_SUFFIXES = (
    "Arabic", "Hebrew", "Devanagari", "Thai", "Korean", "Japanese",
    "JP", "KR", "SC", "TC", "HK", "Armenian", "Georgian", "Bengali",
    "Tamil", "Gujarati", "Gurmukhi", "Kannada", "Malayalam", "Oriya",
    "Sinhala", "Telugu", "Khmer", "Lao", "Myanmar", "Looped", "Naskh",
)
_SCRIPT_SUFFIX_RE = re.compile(
    r"\s+(?:" + "|".join(re.escape(s) for s in _SCRIPT_SUFFIXES) + r")$", re.IGNORECASE
)

# Weight/style descriptors self-hosted @font-face declarations often bake
# into the family name itself (e.g. "Roboto-Regular", "ServiceNow Sans Bold")
# instead of leaving it to a separate weight value — same family, just a
# named cut of it, not a distinct typeface.
_WEIGHT_SUFFIXES = (
    "Thin", "ExtraLight", "Light", "Regular", "Medium", "SemiBold",
    "DemiBold", "Bold", "ExtraBold", "Black", "Heavy", "Italic", "Oblique",
)
_WEIGHT_SUFFIX_RE = re.compile(
    r"[\s-]+(?:" + "|".join(re.escape(s) for s in _WEIGHT_SUFFIXES) + r")$", re.IGNORECASE
)
# Capturing twin of the above — same suffixes, but keeps the matched word so
# it can be converted to a numeric weight instead of just being discarded.
_WEIGHT_SUFFIX_CAPTURE_RE = re.compile(
    r"[\s-]+(" + "|".join(re.escape(s) for s in _WEIGHT_SUFFIXES) + r")$", re.IGNORECASE
)
# "Italic"/"Oblique" describe slant, not boldness — no numeric weight.
_WEIGHT_SUFFIX_TO_NUMERIC = {
    "thin": "100", "extralight": "200", "light": "300", "regular": "400",
    "medium": "500", "semibold": "600", "demibold": "600", "bold": "700",
    "extrabold": "800", "black": "900", "heavy": "900",
}

# Icon/glyph font libraries and generic CSS font-stack keywords that show up
# in scraped `name` values but aren't a deliberate brand typeface choice —
# excluded so they don't inflate a company's distinct-font count or skew its
# style/personality classification.
_NOT_A_TYPEFACE = {
    "swiper-icons", "dashicons", "genericons", "icomoon", "slick",
    "icons-essentials", "font awesome kit", "fontawesome", "font awesome",
    "ui-sans-serif", "ui-monospace", "sans-serif", "serif", "monospace",
    "inherit", "initial", "unset", "cursive", "fantasy", "system-ui",
}

# Universal OS/browser default fonts — the research node's regex-based
# font-family extraction (no real CSS parser) can't tell a font a company
# *deliberately* chose from one that's merely the 2nd/3rd item in some
# unrelated third-party widget's fallback stack (e.g. `font-family: Arial,
# sans-serif` in an embedded script). These render on virtually every site
# that loads no custom font at all, so by definition they're the *absence*
# of a brand choice, not a signal — without this exclusion they single-
# handedly inflated some companies' distinct-font count well past what's
# plausible for a real brand system (rarely more than ~5 typefaces).
_SYSTEM_FALLBACK_FONTS = {
    "arial", "arial black", "helvetica", "helvetica neue", "times new roman",
    "times", "verdana", "tahoma", "trebuchet ms", "georgia", "courier new",
    "courier", "calibri", "segoe ui", "segoe ui symbol", "comic sans ms",
    "impact", "lucida console", "lucida sans unicode", "ms sans serif",
    "ms serif", "geneva", "consolas",
}


def _clean_font_name(name: str) -> str:
    """Undo scraping artifacts before any comparison: Google Fonts URLs leak
    URL-encoding (e.g. "Crimson%20Pro") and sometimes a trailing weight-list
    param (e.g. "Inter%3A400%2C700" -> "Inter:400,700") straight into the
    captured family name."""
    decoded = urllib.parse.unquote(name)
    decoded = re.sub(r":[\d,]+$", "", decoded)
    return decoded.strip()


def _font_family_base(name: str) -> str:
    """Strip trailing script/language and weight/style qualifiers so variants
    of the same typeface collapse to one name, e.g. "IBM Plex Sans Arabic" ->
    "IBM Plex Sans", "ServiceNow Sans Bold" -> "ServiceNow Sans". Leaves
    genuinely distinct families (e.g. "IBM Plex Mono") untouched — those
    aren't script/weight suffixes. Applied repeatedly to unwind compound
    suffixes (e.g. "Noto Sans Arabic Bold")."""
    base = _clean_font_name(name)
    for _ in range(3):
        stripped = _WEIGHT_SUFFIX_RE.sub("", _SCRIPT_SUFFIX_RE.sub("", base)).strip()
        if stripped == base:
            break
        base = stripped
    return base


def _extract_weight_from_name(name: str) -> str | None:
    """Self-hosted @font-face declarations often bake the weight into the
    family name itself (e.g. "Roboto-Regular", "ServiceNow Sans Bold")
    instead of a separate `weight` value. `_font_family_base` strips this
    suffix for display/dedup purposes, but it's real signal that would
    otherwise just be thrown away — recover it as a numeric weight so
    weight-emphasis classification (which only looks at numeric weights)
    doesn't lose it. Most Brandfetch-sourced fonts have no numeric weight at
    all, so without this recovery, most companies had no signal to classify
    on — that's why weight/size emphasis used to leave most companies
    unassigned and collapse to only 2 of 3 possible buckets."""
    match = _WEIGHT_SUFFIX_CAPTURE_RE.search(_clean_font_name(name))
    return _WEIGHT_SUFFIX_TO_NUMERIC.get(match.group(1).lower()) if match else None


def _font_dedup_key(name: str) -> str:
    """Case/hyphen/space-insensitive identity for the same family spelled
    differently across scrapes, e.g. "IBM Plex Sans" vs "ibm-plex-sans", or
    "Crimson Pro" vs "crimson pro" vs "Crimson%20Pro" once decoded."""
    return re.sub(r"[\s\-]+", "", _font_family_base(name)).lower()


def _is_real_typeface(name: str) -> bool:
    base = _font_family_base(name).lower()
    return base not in _NOT_A_TYPEFACE and base not in _SYSTEM_FALLBACK_FONTS


def _clean_fonts_by_domain(fonts_by_domain: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Normalize each company's scraped font list before any interpretation:
    drop icon-glyph/generic-CSS entries, and collapse casing/encoding/script
    variants of the same family (see helpers above) into one entry per
    company, merging their weights/sizes so per-bucket emphasis below still
    sees every scraped value."""
    cleaned: dict[str, list[dict]] = {}
    for domain, fonts in fonts_by_domain.items():
        by_key: dict[str, dict] = {}
        for font in fonts:
            raw_name = font.get("name")
            if not raw_name or not _is_real_typeface(raw_name):
                continue
            base = _font_family_base(raw_name)
            key = _font_dedup_key(raw_name)
            weights = set(font.get("weights") or [])
            recovered_weight = _extract_weight_from_name(raw_name)
            if recovered_weight:
                weights.add(recovered_weight)
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = {
                    "name": base,
                    "weights": sorted(weights),
                    "sizes": list(font.get("sizes") or []),
                }
            else:
                if " " in base and " " not in existing["name"]:
                    existing["name"] = base
                existing["weights"] = sorted(set(existing["weights"]) | weights)
                existing["sizes"] = sorted(set(existing["sizes"]) | set(font.get("sizes") or []))
        if by_key:
            cleaned[domain] = list(by_key.values())
    return cleaned


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
    # persisted fingerprint can never agree on "changed". Cleaning (below)
    # happens only after fingerprinting, so it never affects change-detection.
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
    competitors are an actual "similarity" worth reporting. `fonts_by_domain`
    is expected to already be normalized (see _clean_fonts_by_domain), so
    e.g. "IBM Plex Sans" and "IBM Plex Sans Arabic" already collapsed into
    one shared family before this groups by exact name."""
    by_family: dict[str, set[str]] = {}
    for domain, fonts in fonts_by_domain.items():
        company = domain_to_company(domain)
        for font in fonts:
            name = font.get("name")
            if name:
                by_family.setdefault(name, set()).add(company)
    return {name: companies for name, companies in by_family.items() if len(companies) >= 2}


# rem/em are root/element-relative, not absolute — but the research node
# never captures the base font-size they're relative to, so 16px (the
# universal browser default) is the only sane assumption. pt is a print
# unit some sites still use in CSS (1pt = 1/72in, 96dpi -> 1.333px).
# Without this, every non-"px" size (rem is extremely common — e.g. IBM's
# "0.875rem") silently fell through `_size_bucket` as unmatched, which is
# why most companies had no signal to classify on here.
_PX_PER_UNIT = {"px": 1.0, "rem": 16.0, "em": 16.0, "pt": 1.333}


def _size_bucket(size: str) -> str | None:
    match = re.match(r"([\d.]+)\s*(px|rem|em|pt)$", size.strip(), re.IGNORECASE)
    if not match:
        return None
    value, unit = float(match.group(1)), match.group(2).lower()
    px = value * _PX_PER_UNIT[unit]
    if px < 16:
        return "Compact"
    if px <= 32:
        return "Standard"
    return "Large"


def _classify_size_emphasis(fonts_by_domain: dict[str, list[dict]]) -> dict[str, set[str]]:
    """{bucket: {companies}} — each company's dominant on-page font-size
    bucket across every size value scraped for any of its fonts."""
    buckets: dict[str, set[str]] = {}
    for domain, fonts in fonts_by_domain.items():
        company = domain_to_company(domain)
        counts: dict[str, int] = {}
        for font in fonts:
            for s in font.get("sizes") or []:
                bucket = _size_bucket(s)
                if bucket:
                    counts[bucket] = counts.get(bucket, 0) + 1
        if not counts:
            continue
        dominant = max(counts.items(), key=lambda kv: kv[1])[0]
        buckets.setdefault(dominant, set()).add(company)
    return buckets


def _build_font_usage(fonts_by_domain: dict[str, list[dict]]) -> list[FontUsage]:
    """How many distinct font families each competitor actually uses.
    `fonts_by_domain` is expected to already be normalized (see
    _clean_fonts_by_domain), so this is just a count of what's left."""
    usage = []
    for domain, fonts in fonts_by_domain.items():
        families = sorted({name for f in fonts if (name := f.get("name"))})
        usage.append(FontUsage(
            company=domain_to_company(domain),
            distinct_font_count=len(families),
            font_families=families,
        ))
    return sorted(usage, key=lambda u: u.distinct_font_count, reverse=True)


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
    fonts_by_domain = _clean_fonts_by_domain(fonts_by_domain)
    if not fonts_by_domain:
        logger.warning("visualbranding_fonts_skipped", reason="no_real_typefaces_after_cleaning")
        return {"errors": ["fonts: no real typefaces left after filtering icon/generic fonts"]}

    total_companies = len(fonts_by_domain)
    distinct_names = sorted({
        font.get("name") for fonts in fonts_by_domain.values() for font in fonts if font.get("name")
    })

    openai = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)
    classifications = await _classify_fonts(distinct_names, openai)

    # --- classification / personality (fixed buckets, deterministic assignment) ---
    # Every one of a company's fonts contributes here, not just the first —
    # a company with both a sans-serif body font and a serif display font
    # (e.g. Anthropic: "Anthropic Sans" + "Anthropic Serif") genuinely uses
    # both styles and should show up in both buckets, not get collapsed into
    # whichever font happened to be scraped first.
    classification_buckets: dict[str, set[str]] = {}
    personality_buckets: dict[str, set[str]] = {}
    for domain, fonts in fonts_by_domain.items():
        if not fonts:
            continue
        company = domain_to_company(domain)
        for font in fonts:
            info = classifications.get(font.get("name")) or {}
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

    # --- size emphasis (deterministic from scraped on-page font sizes) ---
    size_buckets = _classify_size_emphasis(fonts_by_domain)
    size_emphasis = [
        DimensionCategory(naming=name, percentage=_pct(len(companies), total_companies), companies=sorted(companies))
        for name, companies in size_buckets.items()
    ]

    # --- usage (deterministic count of distinct font families per company) ---
    usage = _build_font_usage(fonts_by_domain)

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
        size_emphasis=size_emphasis,
        personality=personality,
        usage=usage,
    )

    # --- alerts: only previously-empty-or-different content gets flagged ---
    alerts: list[str] = []
    if previous:
        alerts += diff_named_groups("Font classification", previous.get("classification"), classification)
        alerts += diff_named_groups("Font weight emphasis", previous.get("weight_emphasis"), weight_emphasis)
        alerts += diff_named_groups("Font size emphasis", previous.get("size_emphasis"), size_emphasis)
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
