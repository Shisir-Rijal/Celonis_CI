"""backend/app/agents/sov/nodes/classify.py

Phase 2 of the SoV pipeline: enrich each candidate Mention with theme /
region / relevance / reasoning via a structured-output LLM call.

LLM: gpt-4o-mini, temperature 0, with_structured_output(strict=True).
Parallelism: max 5 concurrent calls (Semaphore).
Failure mode: per-mention exceptions are logged and the mention is dropped —
the run does not abort.

Cheap pre-classification heuristics (language / TLD / source_type) produce
optional hints that the LLM may use or ignore. The LLM still owns the final
decision.
"""

import asyncio
from typing import Any

import structlog
from langchain_openai import ChatOpenAI

from app.agents.sov.state import Mention, SovPipelineState
from app.config import get_settings
from app.prompts.sov.classification import (
    SovClassificationOutput,
    build_classification_messages,
)

logger = structlog.get_logger(__name__)

_CLASSIFY_SEMAPHORE = asyncio.Semaphore(5)
_LLM_MODEL = "gpt-4o-mini"


# ---------------------------------------------------------------------------
# Heuristic pre-classification hints
# ---------------------------------------------------------------------------

_LANG_TO_REGION: dict[str, str] = {
    "de": "DACH",
    "fr": "Europe",
    "es": "Europe",
    "it": "Europe",
    "nl": "Europe",
    "pt": "Europe",
}

_TLD_TO_REGION: dict[str, str] = {
    ".de": "DACH",
    ".at": "DACH",
    ".ch": "DACH",
    ".fr": "Europe",
    ".es": "Europe",
    ".it": "Europe",
    ".nl": "Europe",
    ".uk": "Europe",
    ".com.au": "APAC",
    ".jp": "APAC",
    ".in": "APAC",
}


def _region_hint(mention: Mention) -> str | None:
    """Cheap region guess from language and URL TLD. None = no signal."""
    # SEO is always global in this project (no locale-scoped rankings)
    if mention.source_type == "seo":
        return "Global"

    lang = (mention.language or "")[:2].lower()
    if lang in _LANG_TO_REGION:
        return _LANG_TO_REGION[lang]

    url = mention.url.lower()
    for tld, region in _TLD_TO_REGION.items():
        if tld in url:
            return region

    return None


def _theme_hint(mention: Mention) -> str | None:
    """For SEO, the keyword (already in the title) is itself a theme signal."""
    if mention.source_type != "seo":
        return None
    prefix = "SEO ranking: "
    if mention.title.startswith(prefix):
        return mention.title[len(prefix):]
    return None


# ---------------------------------------------------------------------------
# LLM wiring
# ---------------------------------------------------------------------------

def _build_llm(model: str, temperature: float = 0.0) -> ChatOpenAI:
    """Project-standard ChatOpenAI instance, mirrors geo_intelligence._build_llm."""
    settings = get_settings()
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL or "https://api.openai.com/v1",
    )


async def _classify_one(mention: Mention, structured_llm: Any) -> Mention:
    """Classify one Mention. Returns a new Mention with classification fields set."""
    async with _CLASSIFY_SEMAPHORE:
        messages = build_classification_messages(
            mention,
            region_hint=_region_hint(mention),
            theme_hint=_theme_hint(mention),
        )
        result: SovClassificationOutput = await structured_llm.ainvoke(messages)

    return mention.model_copy(update={
        "themes": result.themes,
        "region": result.region,
        "is_relevant": result.is_relevant,
        "reasoning": result.reasoning,
    })


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------

async def classify_node(state: SovPipelineState) -> dict:
    """Classify every candidate mention. Drop the ones whose LLM call fails."""
    candidates = state["candidate_mentions"]
    if not candidates:
        logger.info("sov_classify_skipped", reason="no_candidates")
        return {"classified_mentions": [], "errors": []}

    structured_llm = _build_llm(_LLM_MODEL).with_structured_output(
        SovClassificationOutput,
        method="json_schema",
        strict=True,
    )

    logger.info("sov_classify_started", candidates=len(candidates))

    tasks = [_classify_one(m, structured_llm) for m in candidates]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    classified: list[Mention] = []
    errors: list[str] = []
    for original, outcome in zip(candidates, results):
        if isinstance(outcome, Exception):
            logger.warning(
                "sov_classify_one_failed",
                url=original.url,
                source_type=original.source_type,
                error=str(outcome),
            )
            errors.append(f"classify:{original.source_type}:{original.url}:{outcome}")
            continue
        classified.append(outcome)

    logger.info(
        "sov_classify_done",
        candidates=len(candidates),
        classified=len(classified),
        failures=len(errors),
    )

    return {
        "classified_mentions": classified,
        "errors": errors,
    }
