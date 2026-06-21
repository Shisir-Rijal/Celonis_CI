"""backend/app/agents/visualbranding/nodes/videos.py

Video interpretation node for the Visual Branding agent.

Reads every active competitor's latest scraped video URLs and source pages
(research_snapshots, node="visuals") and classifies them across four fixed
dimensions (format, effect, length, presence), clusters competitors into
named archetypes, and tallies per-company usage.

NOTE: unlike colors/fonts/logos/images, this node classifies from the video
URL + the page it was scraped from rather than true vision — gpt-4o-mini's
vision input only accepts static images, and no representative video frame
is scraped today (VisualsData.videos only stores url + source_page). If a
future scrape step extracts a thumbnail frame per video, swap
`_classify_videos_text` for an image-based call mirroring images.py exactly.

Only invoked when `detect_changes_node` (graph.py) found the videos
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
    VideoAnalysis,
    VideoArchetype,
    VideoUsage,
    VisualBrandingState,
)
from app.config import get_settings

logger = structlog.get_logger(__name__)

NODE_NAME = "videos"

_FORMATS = ("Product Demo", "Testimonial", "Explainer", "Brand Film")
_EFFECTS = ("Emotional", "Technical", "Aspirational")
_LENGTHS = ("Short (<1min)", "Medium", "Long")
_PRESENCES = ("Captioned", "Voiceover", "Silent")


# ---------------------------------------------------------------------------
# Source data
# ---------------------------------------------------------------------------

async def _build_video_data() -> tuple[dict[str, list[dict]], str]:
    """{domain: [{"url":..., "source_page":...}, ...]} for every active
    competitor with scraped videos, plus a fingerprint of the raw payload
    (must match graph.py's detect_changes_node exactly)."""
    visuals_by_domain = await get_latest_visuals_by_domain()
    videos_dim = extract_dimension(visuals_by_domain, "videos")
    fingerprint = compute_fingerprint(videos_dim)

    videos_by_domain = {d: assets for d, assets in videos_dim.items() if assets}
    return videos_by_domain, fingerprint


def _pct(count: int, total: int) -> float:
    return round(count / total * 100, 1) if total else 0.0


# ---------------------------------------------------------------------------
# Text classification (see module docstring for why not vision)
# ---------------------------------------------------------------------------

async def _classify_videos_text(
    videos_by_domain: dict[str, list[dict]], openai: AsyncOpenAI
) -> dict[str, dict[str, str]]:
    """{domain: {format, effect, length, presence}} — one combined call,
    classifying from each company's representative video URL + the page it
    was found on (no frame data available to inspect)."""
    if not videos_by_domain:
        return {}
    domains = list(videos_by_domain.keys())
    rows = []
    for i, domain in enumerate(domains):
        video = videos_by_domain[domain][0]
        rows.append(
            f'{i}: company="{domain_to_company(domain)}", url="{video.get("url")}", '
            f'found_on="{video.get("source_page") or "unknown"}"'
        )
    try:
        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Each row below describes one company's video by its URL and the page "
                        "it was scraped from. Infer the most likely classification on four "
                        "dimensions (you cannot see the video itself — use the URL/filename and "
                        "page context as your only signal; make a reasonable best guess):\n"
                        f"- format: exactly one of {list(_FORMATS)}\n"
                        f"- effect: exactly one of {list(_EFFECTS)}\n"
                        f"- length: exactly one of {list(_LENGTHS)}\n"
                        f"- presence: exactly one of {list(_PRESENCES)}\n\n"
                        'Return JSON: {"<row index>": {"format": "...", "effect": "...", '
                        '"length": "...", "presence": "..."}, ...} for every row given.'
                    ),
                },
                {"role": "user", "content": "\n".join(rows)},
            ],
            response_format={"type": "json_object"},
        )
        raw = json.loads(response.choices[0].message.content)
        return {domains[int(i)]: v for i, v in raw.items() if i.isdigit() and int(i) < len(domains)}
    except Exception as exc:
        logger.warning("videos_classification_failed", error=str(exc))
        return {}


# ---------------------------------------------------------------------------
# Archetype clustering + naming
# ---------------------------------------------------------------------------

def _cluster_archetypes(
    videos_by_domain: dict[str, list[dict]],
    classifications: dict[str, dict[str, str]],
) -> dict[tuple[str, str], dict]:
    clusters: dict[tuple[str, str], dict] = {}
    for domain, videos in videos_by_domain.items():
        company = domain_to_company(domain)
        info = classifications.get(domain) or {}
        key = (info.get("format", "Product Demo"), info.get("effect", "Technical"))
        bucket = clusters.setdefault(key, {"companies": set(), "thumbnail": videos[0]["url"]})
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
        f'{i}: format="{fmt}", effect="{effect}", companies={sorted(clusters[(fmt, effect)]["companies"])}'
        for i, (fmt, effect) in enumerate(keys)
    ]
    instruction = naming_stability_instruction(previous_names)
    try:
        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Each row below is a video-style cluster (format + effect + which "
                        "competitors use it). Give each cluster a short, evocative archetype "
                        'name (2-4 words, e.g. "Emotional Brand Films", "Technical Walkthroughs") '
                        "and a one-sentence description of what defines the style." + instruction +
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
        logger.warning("videos_archetype_naming_failed", error=str(exc))
        return {
            (fmt, effect): {"name": f"{effect} {fmt}", "description": f"{effect} {fmt.lower()} videos."}
            for fmt, effect in keys
        }


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

async def run(state: VisualBrandingState) -> dict:
    logger.info("visualbranding_videos_started")

    videos_by_domain, fingerprint = await _build_video_data()
    if not videos_by_domain:
        logger.warning("visualbranding_videos_skipped", reason="no_source_data")
        return {"errors": ["videos: no scraped video data available"]}

    total_companies = len(videos_by_domain)
    openai = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)

    classifications = await _classify_videos_text(videos_by_domain, openai)

    dimension_buckets: dict[str, dict[str, set[str]]] = {"format": {}, "effect": {}, "length": {}, "presence": {}}
    defaults = {"format": "Product Demo", "effect": "Technical", "length": "Medium", "presence": "Voiceover"}
    for domain in videos_by_domain:
        company = domain_to_company(domain)
        info = classifications.get(domain) or {}
        for key in dimension_buckets:
            value = info.get(key, defaults[key])
            dimension_buckets[key].setdefault(value, set()).add(company)

    dimension_categories = {
        key: [
            DimensionCategory(naming=name, percentage=_pct(len(companies), total_companies), companies=sorted(companies))
            for name, companies in buckets.items()
        ]
        for key, buckets in dimension_buckets.items()
    }

    previous = get_latest_analysis(NODE_NAME)
    previous_archetype_names = [a.get("naming", "") for a in (previous.get("archetypes") if previous else []) or []]
    clusters = _cluster_archetypes(videos_by_domain, classifications)
    named = await _name_archetypes(clusters, previous_archetype_names, openai)
    archetypes = [
        VideoArchetype(
            naming=named.get(key, {}).get("name", f"{key[1]} {key[0]}"),
            description=named.get(key, {}).get("description", f"{key[1]} {key[0].lower()} videos."),
            thumbnail=cluster["thumbnail"],
            companies=sorted(cluster["companies"]),
        )
        for key, cluster in clusters.items()
    ]

    usage = [
        VideoUsage(company=domain_to_company(domain), count=len(videos), avg_duration_seconds=None)
        for domain, videos in videos_by_domain.items()
    ]

    analysis = VideoAnalysis(
        archetypes=archetypes,
        format=dimension_categories["format"],
        effect=dimension_categories["effect"],
        length=dimension_categories["length"],
        presence=dimension_categories["presence"],
        usage=usage,
    )

    alerts: list[str] = []
    if previous:
        alerts += diff_named_groups("Video archetype", previous.get("archetypes"), archetypes)
        alerts += diff_named_groups("Video format", previous.get("format"), dimension_categories["format"])
        alerts += diff_named_groups("Video effect", previous.get("effect"), dimension_categories["effect"])
        alerts += diff_named_groups("Video length", previous.get("length"), dimension_categories["length"])
        alerts += diff_named_groups("Video presence", previous.get("presence"), dimension_categories["presence"])

    run_at = datetime.now(timezone.utc)
    try:
        insert_visualbranding_snapshot(NODE_NAME, run_at, fingerprint, analysis)
        logger.info("visualbranding_videos_persisted")
    except Exception as exc:
        logger.error("visualbranding_videos_persist_failed", error=str(exc))

    logger.info(
        "visualbranding_videos_done",
        competitors=total_companies,
        archetypes=len(archetypes),
        alerts=len(alerts),
    )
    return {"videos": analysis, "video_alerts": alerts, "completed_nodes": ["videos"]}


if __name__ == "__main__":
    import asyncio
    import truststore

    truststore.inject_into_ssl()  # fixes SSL_CERTIFICATE_VERIFY_FAILED on Windows
    structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

    async def main() -> None:
        result = await run({})
        analysis = result.get("videos")
        if analysis is None:
            print("No analysis produced. Errors:", result.get("errors"))
            return
        print(analysis.model_dump_json(indent=2))
        print("Alerts:", result.get("video_alerts"))

    asyncio.run(main())
