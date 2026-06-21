"""backend/app/agents/visualbranding/nodes/trends.py

Trends synthesis node for the Visual Branding agent.

Fans in from colors/fonts/logos/images/videos (whichever ran this round —
see graph.py) and turns each one's alert fragments (already-meaningful
change descriptions, see alerts.py) into one high-level "where is this
element heading" summary with a direction (up/down/flat).

Elements that didn't run this round (their source data hadn't changed)
keep whatever direction/summary trends last assigned them — read back from
this node's own previous snapshot — so the trends list always covers all
five elements, not just the ones refreshed in the latest run.

Runs in parallel with build_alerts_node, independently fanning in from the
same five interpretation nodes.
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

# state key (alerts) -> element label used in TrendAnalysis / frontend
_ELEMENTS = (
    ("color_alerts", "Color"),
    ("font_alerts", "Font"),
    ("logo_alerts", "Logo"),
    ("image_alerts", "Imagery"),
    ("video_alerts", "Video"),
)

_DIRECTIONS = ("up", "down", "flat")


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
    for alert_key, element in _ELEMENTS:
        alerts = state.get(alert_key)
        if alerts:
            info = await _summarize_changes(element, alerts, openai)
            trends.append(ElementTrend(element=element, direction=info["direction"], summary=info["summary"]))
        elif element in previous_by_element:
            prev = previous_by_element[element]
            trends.append(ElementTrend(element=element, direction=prev["direction"], summary=prev["summary"]))
        # else: never analyzed and nothing changed this round — no entry yet.

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
