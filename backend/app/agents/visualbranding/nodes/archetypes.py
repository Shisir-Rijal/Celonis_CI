"""backend/app/agents/visualbranding/nodes/archetypes.py

Brand archetype synthesis node for the Visual Branding agent.

Unlike colors/fonts/logos/images/videos (each interpreting one raw scraped
dimension), this node synthesizes a holistic "brand archetype" per company
(or group of companies) from every other node's latest *persisted* analysis
— color temperature/hue, font classification/personality, logo type/color,
imagery style/effect, video format. A company can be the sole member of its
own archetype; it doesn't need lookalikes.

Stability is the whole point here (the per-dimension nodes already keep
their own category/archetype *names* stable — see naming.py — but company
membership there is recomputed fresh every run). For brand archetypes, a
company's archetype assignment should only change when its underlying traits
have drifted enough that its previous archetype no longer describes it:

1. For every company, build today's trait signature from whichever
   dimension analyses exist (some may be missing — that's fine, matching
   only looks at keys present on both sides).
2. Compare it against every existing archetype's stored signature. If the
   best match clears `_MATCH_THRESHOLD`, the company stays on that
   archetype — keeping its name, description, and image untouched, even if
   one or two traits shifted slightly.
3. Companies whose best match falls short get grouped by exact signature
   and become brand-new archetypes, LLM-named with naming.py's stability
   instruction so they don't duplicate an existing archetype's name/flavor.
4. Archetypes that lose every member are dropped.

Runs as a third fan-in alongside build_alerts/trends (see graph.py) — not
gated by detect_changes_node, since it depends on the combination of every
dimension's latest state rather than one raw source field.
"""

import json
from collections import Counter
from datetime import datetime, timezone

import structlog
from openai import AsyncOpenAI

from app.agents.visualbranding.naming import naming_stability_instruction
from app.agents.visualbranding.repositories.visualbranding_repository import (
    compute_fingerprint,
    get_latest_analysis,
    insert_visualbranding_snapshot,
)
from app.agents.visualbranding.source_data import domain_to_company, get_latest_visuals_by_domain
from app.agents.visualbranding.state import BrandArchetype, BrandArchetypeAnalysis, VisualBrandingState
from app.config import get_settings

logger = structlog.get_logger(__name__)

NODE_NAME = "brand_archetypes"

# Fraction of trait keys (present on both sides) that must agree for a
# company to be considered "still fitting" its previous archetype.
_MATCH_THRESHOLD = 0.6


# ---------------------------------------------------------------------------
# Signature construction — invert each dimension's company-bucketed output
# ---------------------------------------------------------------------------

def _invert_buckets(categories: list[dict] | None) -> dict[str, str]:
    """[{"naming": "Sans-serif", "companies": [...]}, ...] -> {company: naming}."""
    result: dict[str, str] = {}
    for cat in categories or []:
        for company in cat.get("companies", []):
            result[company] = cat.get("naming")
    return result


def _invert_temperature(colors: dict) -> dict[str, str]:
    result: dict[str, str] = {}
    for label, key in (("warm", "warm"), ("cold", "cold"), ("neutral", "neutral")):
        for company in colors.get(key, []) or []:
            result[company] = label
    return result


def _dominant_hue(diversities: list[dict] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for d in diversities or []:
        hues = d.get("hues") or []
        if not hues:
            continue
        best = max(hues, key=lambda h: len(h.get("colors", [])))
        result[d.get("company")] = best.get("hue_family")
    return result


def _build_signatures(
    colors: dict | None,
    fonts: dict | None,
    logos: dict | None,
    images: dict | None,
    videos: dict | None,
) -> dict[str, dict[str, str]]:
    """{company: {trait_key: value}} from whichever dimension analyses exist."""
    signatures: dict[str, dict[str, str]] = {}

    def set_trait(company: str | None, key: str, value: str | None) -> None:
        if company and value:
            signatures.setdefault(company, {})[key] = value

    if colors:
        for company, value in _invert_temperature(colors).items():
            set_trait(company, "color_temp", value)
        for company, value in _dominant_hue(colors.get("diversities")).items():
            set_trait(company, "color_hue", value)
    if fonts:
        for company, value in _invert_buckets(fonts.get("classification")).items():
            set_trait(company, "font_classification", value)
        for company, value in _invert_buckets(fonts.get("personality")).items():
            set_trait(company, "font_personality", value)
    if logos:
        for company, value in _invert_buckets(logos.get("type")).items():
            set_trait(company, "logo_type", value)
        for company, value in _invert_buckets(logos.get("color")).items():
            set_trait(company, "logo_color", value)
    if images:
        for company, value in _invert_buckets(images.get("style")).items():
            set_trait(company, "image_style", value)
        for company, value in _invert_buckets(images.get("effect")).items():
            set_trait(company, "image_effect", value)
    if videos:
        for company, value in _invert_buckets(videos.get("format")).items():
            set_trait(company, "video_format", value)

    return signatures


def _match_score(sig_a: dict[str, str], sig_b: dict[str, str]) -> float:
    common = set(sig_a) & set(sig_b)
    if not common:
        return 0.0
    matches = sum(1 for k in common if sig_a[k] == sig_b[k])
    return matches / len(common)


def _aggregate_signature(companies: set[str], signatures: dict[str, dict[str, str]]) -> dict[str, str]:
    """Mode (most common value) per trait key across a cluster's current members."""
    keys: set[str] = set()
    for company in companies:
        keys |= set(signatures.get(company, {}))
    aggregate: dict[str, str] = {}
    for key in keys:
        values = [signatures[c][key] for c in companies if key in signatures.get(c, {})]
        if values:
            aggregate[key] = Counter(values).most_common(1)[0][0]
    return aggregate


# ---------------------------------------------------------------------------
# Representative imagery for brand-new clusters
# ---------------------------------------------------------------------------

async def _get_representative_images(companies: set[str]) -> dict[str, str | None]:
    if not companies:
        return {}
    visuals_by_domain = await get_latest_visuals_by_domain()
    result: dict[str, str | None] = {}
    for domain, data in visuals_by_domain.items():
        company = domain_to_company(domain)
        if company not in companies or company in result:
            continue
        images = data.get("images") or []
        logo = data.get("logo") or []
        result[company] = images[0].get("url") if images else (logo[0] if logo else None)
    return result


# ---------------------------------------------------------------------------
# LLM naming for brand-new clusters
# ---------------------------------------------------------------------------

async def _name_new_clusters(
    clusters: dict[tuple, set[str]],
    previous_names: list[str],
    openai: AsyncOpenAI,
) -> dict[tuple, dict]:
    """{cluster key -> {"name", "keywords", "vibe", "typography", "coloring"}}."""
    if not clusters:
        return {}
    keys = list(clusters.keys())
    rows = []
    for i, key in enumerate(keys):
        traits = dict(key)
        rows.append(f"{i}: traits={traits}, companies={sorted(clusters[key])}")
    instruction = naming_stability_instruction(previous_names)
    try:
        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Each row below describes one competitive brand-identity cluster: its "
                        "underlying traits (color temperature/hue, font classification/"
                        "personality, logo type/color, imagery style/effect, video format) and "
                        "which companies share them. A cluster may contain just one company.\n\n"
                        "For each row, invent a short, evocative brand archetype name (2-4 words, "
                        'e.g. "Bold Technical Disruptor", "Calm Enterprise Trust"), 3-5 single-word '
                        "keywords capturing its vibe, and one-sentence summaries each for overall "
                        "vibe, typography, and coloring." + instruction +
                        ' Return JSON: {"<row index>": {"name": "...", "keywords": ["...", ...], '
                        '"vibe": "...", "typography": "...", "coloring": "..."}, ...} for every '
                        "row given."
                    ),
                },
                {"role": "user", "content": "\n".join(rows)},
            ],
            response_format={"type": "json_object"},
        )
        raw = json.loads(response.choices[0].message.content)
        return {key: raw.get(str(i), {}) for i, key in enumerate(keys)}
    except Exception as exc:
        logger.warning("archetypes_naming_failed", error=str(exc))
        return {
            key: {
                "name": "Emerging Style",
                "keywords": [],
                "vibe": "Distinct visual identity not yet seen in this competitive set.",
                "typography": "",
                "coloring": "",
            }
            for key in keys
        }


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

async def run(state: VisualBrandingState) -> dict:
    logger.info("visualbranding_archetypes_started")

    colors = get_latest_analysis("colors")
    fonts = get_latest_analysis("fonts")
    logos = get_latest_analysis("logos")
    images = get_latest_analysis("images")
    videos = get_latest_analysis("videos")

    signatures = _build_signatures(colors, fonts, logos, images, videos)
    if not signatures:
        logger.info("visualbranding_archetypes_skipped", reason="no_dimension_analyses_yet")
        return {}

    previous = get_latest_analysis(NODE_NAME)
    previous_archetypes = (previous or {}).get("archetypes") or []

    # Step 1: keep every company on its previous archetype if it still fits well.
    kept: dict[int, set[str]] = {i: set() for i in range(len(previous_archetypes))}
    unassigned: list[str] = []
    for company, sig in signatures.items():
        best_idx, best_score = None, 0.0
        for i, arche in enumerate(previous_archetypes):
            score = _match_score(sig, arche.get("signature") or {})
            if score > best_score:
                best_idx, best_score = i, score
        if best_idx is not None and best_score >= _MATCH_THRESHOLD:
            kept[best_idx].add(company)
        else:
            unassigned.append(company)

    # Step 2: companies that no longer fit get grouped into brand-new clusters
    # by exact signature match (only companies with the *same* drifted
    # profile share a new archetype).
    new_clusters: dict[tuple, set[str]] = {}
    for company in unassigned:
        key = tuple(sorted(signatures[company].items()))
        new_clusters.setdefault(key, set()).add(company)

    openai = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)
    previous_names = [a.get("naming", "") for a in previous_archetypes]
    representative_images = await _get_representative_images(
        {c for cluster in new_clusters.values() for c in cluster}
    )
    named_new = await _name_new_clusters(new_clusters, previous_names, openai)

    archetypes: list[BrandArchetype] = []
    reassigned = 0
    for i, arche in enumerate(previous_archetypes):
        companies = kept[i]
        if not companies:
            continue  # archetype lost every member this round — drop it
        if set(arche.get("companies", [])) != companies:
            reassigned += 1
        archetypes.append(
            BrandArchetype(
                naming=arche["naming"],
                keywords=arche.get("keywords", []),
                vibe=arche.get("vibe", ""),
                typography=arche.get("typography", ""),
                coloring=arche.get("coloring", ""),
                sample_image=arche.get("sample_image"),
                companies=sorted(companies),
                signature=_aggregate_signature(companies, signatures),
            )
        )
    for key, companies in new_clusters.items():
        info = named_new.get(key, {})
        sample_image = next(
            (representative_images.get(c) for c in sorted(companies) if representative_images.get(c)),
            None,
        )
        archetypes.append(
            BrandArchetype(
                naming=info.get("name", "Emerging Style"),
                keywords=info.get("keywords", []),
                vibe=info.get("vibe", ""),
                typography=info.get("typography", ""),
                coloring=info.get("coloring", ""),
                sample_image=sample_image,
                companies=sorted(companies),
                signature=dict(key),
            )
        )

    analysis = BrandArchetypeAnalysis(archetypes=archetypes)

    run_at = datetime.now(timezone.utc)
    try:
        fingerprint = compute_fingerprint(signatures)
        insert_visualbranding_snapshot(NODE_NAME, run_at, fingerprint, analysis)
        logger.info("visualbranding_archetypes_persisted")
    except Exception as exc:
        logger.error("visualbranding_archetypes_persist_failed", error=str(exc))

    logger.info(
        "visualbranding_archetypes_done",
        archetypes=len(archetypes),
        new_clusters=len(new_clusters),
        reassigned=reassigned,
    )
    return {"brand_archetypes": analysis, "completed_nodes": ["brand_archetypes"]}


if __name__ == "__main__":
    import asyncio
    import truststore

    truststore.inject_into_ssl()  # fixes SSL_CERTIFICATE_VERIFY_FAILED on Windows
    structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

    async def main() -> None:
        result = await run({})
        analysis = result.get("brand_archetypes")
        if analysis is None:
            print("No analysis produced (no dimension analyses persisted yet).")
            return
        print(analysis.model_dump_json(indent=2))

    asyncio.run(main())
