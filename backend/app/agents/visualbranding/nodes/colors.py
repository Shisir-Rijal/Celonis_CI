"""backend/app/agents/visualbranding/nodes/colors.py

Color interpretation node for the Visual Branding agent.

Reads every active competitor's latest scraped colors (research_snapshots,
node="visuals"), clusters them into hue families, and produces the
cross-competitor ColorAnalysis that backs the branding page's Color
Comparison section (spectrum, per-company diversity, warm/cool split).

Only invoked when `detect_changes_node` (graph.py) found the colors
dimension changed since this node's last run.
"""

import json
from datetime import datetime, timezone

import structlog
from openai import AsyncOpenAI

from app.agents.visualbranding.alerts import diff_company_lists, diff_named_groups
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
    ColorAnalysis,
    ColorDiversity,
    ColorSpectrum,
    HueGroup,
    VisualBrandingState,
    WarmCoolEntry,
)
from app.config import get_settings

logger = structlog.get_logger(__name__)

NODE_NAME = "colors"

# 8-bucket hue classification — matches the frontend's color-family naming
# (ColorComparison.tsx / hue wheel) closely enough to read consistently
# across the dashboard.
_HUE_FAMILIES: list[tuple[float, float, str]] = [
    (0, 15, "Red"),
    (15, 45, "Orange"),
    (45, 70, "Yellow"),
    (70, 160, "Green"),
    (160, 200, "Teal"),
    (200, 255, "Blue"),
    (255, 290, "Purple"),
    (290, 345, "Pink"),
    (345, 360, "Red"),
]


# ---------------------------------------------------------------------------
# Pure helpers — hue math
# ---------------------------------------------------------------------------

def _hex_to_hue(hex_code: str) -> float | None:
    """Hue angle (0-360), or None for near-grayscale colors with no meaningful hue.

    Threshold is 0.12 (~30/255 channel spread), not just-barely-not-gray —
    colors like a near-black navy (#20262F, spread=15) or a beige-grey
    (#AEACA0, spread=14) technically aren't pure grayscale but read as
    neutral to a human eye. At the old 0.04 threshold they still cleared the
    bar and got clustered into a real hue family (e.g. "Blue"), which both
    polluted that family's company count and skewed warm/cool voting — one
    such barely-chromatic secondary color was enough to flip a company's
    whole secondary-palette temperature in a 50/50 tie.
    """
    clean = hex_code.lstrip("#")
    if len(clean) != 6:
        return None
    try:
        r, g, b = (int(clean[i : i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return None
    hi, lo = max(r, g, b), min(r, g, b)
    delta = hi - lo
    if delta < 0.12:
        return None
    if hi == r:
        hue = ((g - b) / delta) % 6
    elif hi == g:
        hue = (b - r) / delta + 2
    else:
        hue = (r - g) / delta + 4
    hue *= 60
    return hue if hue >= 0 else hue + 360


def _lightness(hex_code: str) -> float | None:
    """HSL lightness (0=black, 1=white), or None if not a valid 6-digit hex."""
    clean = hex_code.lstrip("#")
    if len(clean) != 6:
        return None
    try:
        r, g, b = (int(clean[i : i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return None
    return (max(r, g, b) + min(r, g, b)) / 2


def _hue_family(hue: float | None, hex_code: str | None = None) -> str:
    """Grayscale colors (hue is None) used to all collapse into one generic
    "Neutral" bucket — but a near-black and a near-white both read as
    "neutral" by hue alone, even though they're visually and brand-wise very
    different swatches (e.g. "we lean on black" vs. "we lean on white").
    Split by lightness instead: only true mid-grays stay "Neutral"."""
    if hue is None:
        lightness = _lightness(hex_code) if hex_code else None
        if lightness is None:
            return "Neutral"
        if lightness < 0.35:
            return "Black"
        if lightness > 0.65:
            return "White"
        return "Neutral"
    for lo, hi, name in _HUE_FAMILIES:
        if lo <= hue < hi:
            return name
    return "Neutral"


def _is_warm(hue: float | None) -> bool | None:
    """True = warm, False = cool, None = neutral/grayscale (no vote)."""
    if hue is None:
        return None
    return hue < 75 or hue >= 290


# ---------------------------------------------------------------------------
# Source data
# ---------------------------------------------------------------------------

async def _build_color_data() -> tuple[dict[str, dict[str, list[str]]], str]:
    """{domain: {"primary": [...], "secondary": [...]}} for every active
    competitor with scraped colors, plus a fingerprint of that exact payload
    for change-detection (must match what graph.py fingerprints, or the
    router and this node could disagree about whether anything changed)."""
    visuals_by_domain = await get_latest_visuals_by_domain()
    colors_by_domain = extract_dimension(visuals_by_domain, "colors")
    # Fingerprint the raw extract_dimension result — must match exactly what
    # graph.py's detect_changes_node hashes, or the router and this node's
    # persisted fingerprint can never agree on "changed" (filtering first
    # would hash a different payload than the router compares against).
    fingerprint = compute_fingerprint(colors_by_domain)
    colors_by_domain = {d: c for d, c in colors_by_domain.items() if c}
    return colors_by_domain, fingerprint


# ---------------------------------------------------------------------------
# Interpretation
# ---------------------------------------------------------------------------

def _cluster_hue_families(
    colors_by_domain: dict[str, dict[str, list[str]]],
) -> dict[str, set[str]]:
    """{hue_family: {companies using it}} across every competitor's full
    palette — includes "Neutral" (black/white/grey) as its own family so the
    spectrum shows it too, not just the chromatic hues."""
    families: dict[str, set[str]] = {}
    for domain, palette in colors_by_domain.items():
        company = domain_to_company(domain)
        all_hexes = (palette.get("primary") or []) + (palette.get("secondary") or [])
        for hex_code in all_hexes:
            family = _hue_family(_hex_to_hue(hex_code), hex_code)
            families.setdefault(family, set()).add(company)
    return families


def _representative_hex(family: str, colors_by_domain: dict[str, dict[str, list[str]]]) -> str:
    """First hex that maps to this hue family — good enough as a representative
    swatch; not trying to average/blend colors within a family."""
    for palette in colors_by_domain.values():
        for hex_code in (palette.get("primary") or []) + (palette.get("secondary") or []):
            if _hue_family(_hex_to_hue(hex_code), hex_code) == family:
                return hex_code
    return "#CCCCCC"


def _build_diversities(colors_by_domain: dict[str, dict[str, list[str]]]) -> list[ColorDiversity]:
    diversities: list[ColorDiversity] = []
    for domain, palette in colors_by_domain.items():
        company = domain_to_company(domain)
        all_hexes = (palette.get("primary") or []) + (palette.get("secondary") or [])
        hues: dict[str, list[str]] = {}
        for hex_code in all_hexes:
            family = _hue_family(_hex_to_hue(hex_code), hex_code)
            hues.setdefault(family, []).append(hex_code)
        diversities.append(
            ColorDiversity(
                company=company,
                count=len(hues),
                hues=[HueGroup(hue_family=f, colors=cs) for f, cs in hues.items()],
                secondary_hexes=palette.get("secondary") or [],
            )
        )
    return sorted(diversities, key=lambda d: d.count, reverse=True)


def _classify_temperature(hexes: list[str]) -> str:
    """Majority-vote warm/cool across a set of hexes; "neutral" if none of
    them carry a meaningful hue (e.g. all black/white/grey, or the set is
    empty)."""
    votes = [v for v in (_is_warm(_hex_to_hue(h)) for h in hexes) if v is not None]
    if not votes:
        return "neutral"
    return "warm" if sum(votes) >= len(votes) / 2 else "cool"


def _build_warm_cool_breakdown(
    colors_by_domain: dict[str, dict[str, list[str]]],
) -> list[WarmCoolEntry]:
    """Classify each company's temperature three ways — primary-only,
    secondary-only, and the full combined palette — so the frontend can
    filter the Warm vs. Cool card by color type without re-deriving hue math
    client-side or a separate API round trip."""
    breakdown: list[WarmCoolEntry] = []
    for domain, palette in colors_by_domain.items():
        company = domain_to_company(domain)
        primary_hexes = palette.get("primary") or []
        secondary_hexes = palette.get("secondary") or []
        breakdown.append(
            WarmCoolEntry(
                company=company,
                primary=_classify_temperature(primary_hexes) if primary_hexes else None,
                secondary=_classify_temperature(secondary_hexes) if secondary_hexes else None,
                overall=_classify_temperature(primary_hexes + secondary_hexes),
            )
        )
    return breakdown


async def _describe_buckets(
    entries: list[tuple[str, str, str, list[str]]],  # (entry_key, family, hex, companies)
    openai: AsyncOpenAI,
) -> dict[str, str]:
    """One combined LLM call: short brand/psychology association text per
    hue-family entry (each usage tier can hold several — see `run()`)."""
    prompt_rows = [
        f'{key}: family="{family}", companies={companies}' for key, family, _, companies in entries
    ]
    try:
        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "For each color-usage entry below, write one short sentence (max 20 "
                        "words) on the brand/psychological association of that hue family in "
                        "this competitive set. Return JSON: "
                        '{"<key>": "<sentence>", ...} for every key given.'
                    ),
                },
                {"role": "user", "content": "\n".join(prompt_rows)},
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as exc:
        logger.warning("colors_description_failed", error=str(exc))
        return {
            key: f"{family} is used by {len(companies)} tracked competitor(s)."
            for key, family, _, companies in entries
        }


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

async def run(state: VisualBrandingState) -> dict:
    logger.info("visualbranding_colors_started")

    colors_by_domain, fingerprint = await _build_color_data()
    if not colors_by_domain:
        logger.warning("visualbranding_colors_skipped", reason="no_source_data")
        return {"errors": ["colors: no scraped color data available"]}

    families = _cluster_hue_families(colors_by_domain)
    if not families:
        logger.warning("visualbranding_colors_skipped", reason="no_chromatic_colors")
        return {"errors": ["colors: no chromatic (non-grayscale) colors found"]}

    # Rank hue families by how many distinct companies use them — frequency
    # as a proxy for "real differentiator" (same logic the research node's
    # own CSS color ranking already uses). Bucket by *absolute* company count
    # rather than picking one fixed index per tier — otherwise a family like
    # "Red" can rank 2nd/3rd most popular and never appear anywhere in the
    # spectrum just because only 4 indices were sampled.
    #
    # These thresholds are for the *combined* (primary+secondary) palette —
    # i.e. the frontend's "all" filter — and are deliberately higher than the
    # primary-only/secondary-only thresholds the frontend applies client-side
    # (ColorComparison.tsx's `usageLabelForFiltered`, 3=common/>3=very_common).
    # A color counted under "all" qualifies by being used as *either* role, so
    # its company count is naturally larger than either role counted alone —
    # using the same low thresholds here would make almost everything
    # "very_common" and collapse the spectrum's lower tiers to empty.
    ranked = sorted(families.items(), key=lambda kv: len(kv[1]), reverse=True)

    def _usage_label(company_count: int) -> str:
        if company_count > 6:
            return "very_common"
        if company_count >= 5:
            return "common"
        if company_count >= 3:
            return "occasional"
        return "rare"

    grouped: dict[str, list[tuple[str, str, list[str]]]] = {
        "very_common": [], "common": [], "occasional": [], "rare": []
    }
    for family, companies in ranked:
        label = _usage_label(len(companies))
        grouped[label].append((family, _representative_hex(family, colors_by_domain), sorted(companies)))

    entries = [
        (f"{label}:{family}", family, hex_code, companies)
        for label, items in grouped.items()
        for family, hex_code, companies in items
    ]

    openai = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)
    descriptions = await _describe_buckets(entries, openai)

    spectrum: dict[str, list[ColorSpectrum]] = {
        label: [
            ColorSpectrum(
                type=family,
                color=hex_code,
                companies=companies,
                description=descriptions.get(
                    f"{label}:{family}", f"{family} is used by {len(companies)} tracked competitor(s)."
                ),
            )
            for family, hex_code, companies in items
        ]
        for label, items in grouped.items()
    }

    warm_cool_breakdown = _build_warm_cool_breakdown(colors_by_domain)
    warm = sorted(e.company for e in warm_cool_breakdown if e.overall == "warm")
    cool = sorted(e.company for e in warm_cool_breakdown if e.overall == "cool")
    neutral = sorted(e.company for e in warm_cool_breakdown if e.overall == "neutral")

    analysis = ColorAnalysis(
        very_common=spectrum["very_common"],
        common=spectrum["common"],
        occasional=spectrum["occasional"],
        rare=spectrum["rare"],
        diversities=_build_diversities(colors_by_domain),
        warm_cool_breakdown=warm_cool_breakdown,
        warm=warm,
        cold=cool,
        neutral=neutral,
    )

    # Compare against the previous run's stored analysis — only a previously
    # empty bucket or an actual company-membership change is worth flagging
    # (see alerts.py); cosmetic/no-op diffs produce no fragment.
    previous = get_latest_analysis(NODE_NAME)
    alerts: list[str] = []
    if previous:
        for label, key in (
            ("Very common color", "very_common"),
            ("Common color", "common"),
            ("Occasional color", "occasional"),
            ("Rare color", "rare"),
        ):
            alerts += diff_named_groups(label, previous.get(key), getattr(analysis, key), name_field="type")
        for label, key in (("Warm companies", "warm"), ("Cold companies", "cold"), ("Neutral companies", "neutral")):
            fragment = diff_company_lists(label, previous.get(key), getattr(analysis, key))
            if fragment:
                alerts.append(fragment)

    run_at = datetime.now(timezone.utc)
    try:
        insert_visualbranding_snapshot(NODE_NAME, run_at, fingerprint, analysis)
        logger.info("visualbranding_colors_persisted")
    except Exception as exc:
        logger.error("visualbranding_colors_persist_failed", error=str(exc))

    logger.info("visualbranding_colors_done", families=len(ranked), competitors=len(colors_by_domain), alerts=len(alerts))
    return {"colors": analysis, "color_alerts": alerts, "completed_nodes": ["colors"]}


if __name__ == "__main__":
    # No per-company arg: this node always pulls every active competitor
    # (competitors table, active=True) and produces one cross-competitor
    # analysis — run against whatever real data already exists in Supabase.
    import asyncio
    import truststore

    truststore.inject_into_ssl()  # fixes SSL_CERTIFICATE_VERIFY_FAILED on Windows
    structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

    async def main() -> None:
        result = await run({})
        analysis = result.get("colors")
        if analysis is None:
            print("No analysis produced. Errors:", result.get("errors"))
            return
        print(analysis.model_dump_json(indent=2))

    asyncio.run(main())
