"""Report generation agent.

Orchestrates the full pipeline: load data -> build prompt -> call LLM -> return markdown.
Adding a new topic only requires a new loader and prompt — nothing else changes here.
"""

import structlog
from app.llm import get_chat_client
from .loaders.news import NewsReportLoader
from .loaders.events import EventsReportLoader
from .loaders.geo import GeoReportLoader
from .loaders.branding import BrandingReportLoader
from .prompts.news import build_news_prompt
from .prompts.events import build_events_prompt
from .prompts.geo import build_geo_prompt
from .prompts.branding import build_branding_prompt

logger = structlog.get_logger(__name__)

LOADERS = {
    "news": NewsReportLoader,
    "events": EventsReportLoader,
    "geo": GeoReportLoader,
    "branding": BrandingReportLoader,
}

PROMPT_BUILDERS = {
    "news": build_news_prompt,
    "events": build_events_prompt,
    "geo": build_geo_prompt,
    "branding": build_branding_prompt,
}


async def generate_report(topic: str, companies: list[str] | None = None) -> str:
    """Fetch data for the given topic, call the LLM, and return a markdown report.

    Args:
        topic: One of 'news', 'events', 'geo', 'branding'.
        companies: Optional list of company domains to filter by.
                   Ignored for branding (always cross-competitor).

    Returns:
        Markdown string ready to display or export.

    Raises:
        ValueError: Unknown topic.
        RuntimeError: LLM or data fetch failed.
    """
    if topic not in LOADERS:
        raise ValueError(f"Unknown report topic '{topic}'. Valid topics: {list(LOADERS)}")

    logger.info("report_generation_started", topic=topic, companies=companies)

    # Step 1: load data
    loader_cls = LOADERS[topic]
    loader = loader_cls(companies=companies if topic != "branding" else None)
    try:
        data = await loader.fetch()
    except Exception as exc:
        logger.error("report_data_fetch_failed", topic=topic, error=str(exc))
        raise RuntimeError(f"Failed to fetch data for topic '{topic}'.") from exc

    # Step 2: build prompt
    build_prompt = PROMPT_BUILDERS[topic]
    system_prompt, user_prompt = build_prompt(data)

    # Step 3: call LLM
    try:
        client = get_chat_client()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        markdown = await client.complete(messages)
    except Exception as exc:
        logger.error("report_llm_call_failed", topic=topic, error=str(exc))
        raise RuntimeError("LLM call failed during report generation.") from exc

    logger.info("report_generation_complete", topic=topic, length=len(markdown))
    return markdown