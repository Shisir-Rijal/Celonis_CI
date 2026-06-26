"""backend/app/agents/visualbranding/nodes/trends.py

Trends synthesis node for the Visual Branding agent.

Fans in from colors/fonts/logos/images (whichever ran this round — see
graph.py) and turns each one's alert fragments (already-meaningful change
descriptions, see alerts.py) into one high-level "where is this element
heading" summary with a direction (up/down/flat). Video is intentionally
excluded here — it isn't surfaced in the Visual Trends UI.

Elements that didn't run this round (their source data hadn't changed)
keep whatever direction/summary trends last assigned them — read back from
this node's own previous snapshot — so the trends list always covers all
four elements, not just the ones refreshed in the latest run.

Runs in parallel with build_alerts_node, independently fanning in from the
same four interpretation nodes.
"""

import json
from datetime import datetime, timezone

import structlog
from openai import AsyncOpenAI

from app.agents.visualbranding.repositories.visualbranding_repository import (
    compute_fingerprint,
    get_latest_analysis,
    insert_visualbranding_snapshot,
)
from app.agents.visualbranding.state import ElementTrend, TrendAnalysis, VisualBrandingState
from app.config import get_settings

logger = structlog.get_logger(__name__)

NODE_NAME = "trends"

# (alert state key, element label, node name) — node name is whose own
# latest analysis the headline stat is computed from, read independently via
# get_latest_analysis rather than from this run's graph `state`, so a
# headline is always available even in rounds where that element's node
# didn't re-run (its source data hadn't changed) — the same "fall back to
# last known good" approach already used for direction/summary continuity.
_ELEMENT_INFO = (
    ("color_alerts", "Color", "colors"),
    ("font_alerts", "Font", "fonts"),
    ("logo_alerts", "Logo", "logos"),
    ("image_alerts", "Imagery", "images"),
)

_DIRECTIONS = ("up", "down", "flat")


# ---------------------------------------------------------------------------
# Headline stat — "the single most common trait" per element
# ---------------------------------------------------------------------------

def _dominant_bucket(
    categories: list[dict], exclude: set[str] | None = None
) -> tuple[str, int] | None:
    """(name, company_count) of the largest DimensionCategory bucket, skipping
    any value in `exclude` — a generic catch-all (e.g. signal_shape's "None"
    for purely typographic logos) wouldn't make a meaningful one-word
    headline even if it happens to be the largest bucket."""
    best: tuple[str, list] | None = None
    for c in categories or []:
        name = c.get("naming")
        if exclude and name in exclude:
            continue
        companies = c.get("companies") or []
        if not companies:
            continue
        if best is None or len(companies) > len(best[1]):
            best = (name, companies)
    return (best[0], len(best[1])) if best else None


def _total_companies(categories: list[dict]) -> int:
    return len({c for cat in (categories or []) for c in (cat.get("companies") or [])})


def _dominant_primary_hue(color_data: dict) -> tuple[str, int, int] | None:
    """(hue_family, company_count, total_companies) for the hue family used as
    a *primary* color by the most companies — diversities already record each
    company's hexes per hue family plus which of those hexes are secondary,
    so a hue only counts here if at least one of a company's hexes in that
    family isn't in its secondary set."""
    diversities = color_data.get("diversities") or []
    if not diversities:
        return None
    family_companies: dict[str, set[str]] = {}
    for d in diversities:
        company = d.get("company")
        secondary = set(d.get("secondary_hexes") or [])
        for h in d.get("hues") or []:
            family = h.get("hue_family")
            colors = h.get("colors") or []
            if family and any(c not in secondary for c in colors):
                family_companies.setdefault(family, set()).add(company)
    if not family_companies:
        return None
    family, companies = max(family_companies.items(), key=lambda kv: len(kv[1]))
    return family, len(companies), len(diversities)


def _logo_headline(data: dict) -> tuple[str, int, int, str] | None:
    """(name, count, total, kind_word) — prefers signal_shape (a true visual
    motif, e.g. "Circle") over the more generic shape_style (e.g. "Rounded"),
    skipping signal_shape's "None" bucket (purely typographic logos) since
    that's an absence of a motif, not one worth highlighting."""
    signal = _dominant_bucket(data.get("signal_shape") or [], exclude={"None"})
    if signal:
        return signal[0], signal[1], _total_companies(data.get("signal_shape")), "motif"
    shape = _dominant_bucket(data.get("shape_style") or [])
    if shape:
        return shape[0], shape[1], _total_companies(data.get("shape_style")), "shape"
    return None


def _article(word: str) -> str:
    return "an" if word[:1].upper() in "AEIOU" else "a"


def _headline_change_note(previous: dict | None, headline: str, count: int) -> str:
    if not previous or previous.get("headline") != headline or previous.get("headline_count") is None:
        return ""
    prev_count = previous["headline_count"]
    if count == prev_count:
        return " — unchanged since the last run"
    return f" — {'up' if count > prev_count else 'down'} from {prev_count}"


def _compute_headline(element: str, node_name: str, previous: dict | None) -> dict | None:
    data = get_latest_analysis(node_name)
    if not data:
        return None

    if element == "Color":
        result = _dominant_primary_hue(data)
        if not result:
            return None
        headline, count, total = result
        detail = f"{count} of {total} competitors use {headline} as a primary color"
    elif element == "Logo":
        result = _logo_headline(data)
        if not result:
            return None
        headline, count, total, kind = result
        detail = f"{count} of {total} competitors share {_article(headline)} {headline} logo {kind}"
    elif element == "Imagery":
        result = _dominant_bucket(data.get("style") or [])
        if not result:
            return None
        headline, count = result
        total = _total_companies(data.get("style"))
        detail = f"{count} of {total} competitors use {_article(headline)} {headline} visual style"
    elif element == "Font":
        result = _dominant_bucket(data.get("classification") or [])
        if not result:
            return None
        headline, count = result
        total = _total_companies(data.get("classification"))
        detail = f"{count} of {total} competitors use a {headline} typeface"
    else:
        return None

    detail += _headline_change_note(previous, headline, count)
    return {"headline": headline, "headline_detail": detail, "headline_count": count}


async def _summarize_changes(
    element: str, alerts: list[str], openai: AsyncOpenAI
) -> dict[str, str]:
    """{"direction": "up"|"down"|"flat", "summary": "..."} from one element's
    raw change fragments."""
    try:
        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"Below are the changes detected this run for the '{element}' dimension "
                        "of a competitive visual-branding analysis. Summarize them in one short "
                        "sentence (max 25 words), and classify the overall direction: \"up\" if "
                        "competitors are diversifying/adopting more variety, \"down\" if they're "
                        "consolidating/converging on fewer styles, \"flat\" if the change is "
                        'minor or directionless. Return JSON: {"direction": "up|down|flat", '
                        '"summary": "..."}.'
                    ),
                },
                {"role": "user", "content": "\n".join(alerts)},
            ],
            response_format={"type": "json_object"},
        )
        raw = json.loads(response.choices[0].message.content)
        direction = raw.get("direction") if raw.get("direction") in _DIRECTIONS else "flat"
        return {"direction": direction, "summary": raw.get("summary", "")}
    except Exception as exc:
        logger.warning("trends_summarize_failed", element=element, error=str(exc))
        return {"direction": "flat", "summary": f"{len(alerts)} change(s) detected."}


async def run(state: VisualBrandingState) -> dict:
    logger.info("visualbranding_trends_started")

    previous = get_latest_analysis(NODE_NAME)
    previous_by_element = {t["element"]: t for t in (previous.get("trends") if previous else []) or []}

    openai = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)

    trends: list[ElementTrend] = []
    for alert_key, element, node_name in _ELEMENT_INFO:
        alerts = state.get(alert_key)
        prev = previous_by_element.get(element)
        if alerts:
            info = await _summarize_changes(element, alerts, openai)
            direction, summary = info["direction"], info["summary"]
        elif prev:
            direction, summary = prev["direction"], prev["summary"]
        else:
            direction, summary = "flat", "No changes detected yet."

        headline_info = _compute_headline(element, node_name, prev)
        if not headline_info and not alerts and not prev:
            # Nothing to say at all for this element yet (never analyzed,
            # nothing changed, no headline data either) — skip it rather
            # than show an empty/meaningless card.
            continue

        trends.append(ElementTrend(element=element, direction=direction, summary=summary, **(headline_info or {})))

    if not trends:
        logger.info("visualbranding_trends_skipped", reason="no_changed_dimensions_and_no_history")
        return {}

    analysis = TrendAnalysis(trends=trends)

    run_at = datetime.now(timezone.utc)
    try:
        fingerprint = compute_fingerprint(analysis.model_dump(mode="json"))
        insert_visualbranding_snapshot(NODE_NAME, run_at, fingerprint, analysis)
        logger.info("visualbranding_trends_persisted")
    except Exception as exc:
        logger.error("visualbranding_trends_persist_failed", error=str(exc))

    logger.info("visualbranding_trends_done", elements=len(trends))
    return {"trends": analysis, "completed_nodes": ["trends"]}
