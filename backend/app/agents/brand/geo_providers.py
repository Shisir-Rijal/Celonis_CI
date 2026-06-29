"""LLM provider configurations for GEO Intelligence queries.

Phase 1 (raw keyword queries) runs on every configured provider.
Phase 2 (structured analysis) and Phase 4 (synthesis) always use OpenAI —
structured JSON schema output is consistent and cheap there.

A provider is active when its API key is present in settings. OpenAI is
always active. Claude and Perplexity are opt-in.
"""

from dataclasses import dataclass

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.config import get_settings

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Model constants
# ---------------------------------------------------------------------------

_GPT_MODEL = "gpt-5.5"
_CLAUDE_MODEL = "claude-sonnet-4-6"
_PERPLEXITY_MODEL = "sonar-pro"
_PERPLEXITY_BASE_URL = "https://api.perplexity.ai"

# Synthesis uses gpt-5.5 — stronger strategic reasoning than o4-mini and
# supports strict JSON schema output at temperature=0.0.
_SYNTHESIS_MODEL = "gpt-5.5"


# ---------------------------------------------------------------------------
# Provider dataclass
# ---------------------------------------------------------------------------

@dataclass
class GeoQueryProvider:
    """One LLM used for Phase 1 GEO keyword queries."""

    name: str          # written to brand_geo_sightings.llm
    llm: BaseChatModel


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------

def build_query_providers() -> list[GeoQueryProvider]:
    """Return all active GEO query providers.

    OpenAI is always included. Claude and Perplexity are included only when
    their API keys are present in settings. Call once per pipeline run —
    provider list is derived from settings at call time.
    """
    settings = get_settings()
    providers: list[GeoQueryProvider] = [
        GeoQueryProvider(
            name=_GPT_MODEL,
            llm=ChatOpenAI(
                model=_GPT_MODEL,
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL or "https://api.openai.com/v1",
                temperature=0.0,
            ),
        )
    ]

    if settings.ANTHROPIC_API_KEY:
        providers.append(GeoQueryProvider(
            name=_CLAUDE_MODEL,
            llm=ChatAnthropic(
                model=_CLAUDE_MODEL,
                api_key=settings.ANTHROPIC_API_KEY,
                temperature=0.0,
            ),
        ))
        logger.info("geo_provider_enabled", provider="claude", model=_CLAUDE_MODEL)

    if settings.PERPLEXITY_API_KEY:
        # Perplexity exposes an OpenAI-compatible endpoint. sonar-pro uses
        # live web search — it directly measures AI search engine visibility,
        # which is what GEO tracks.
        providers.append(GeoQueryProvider(
            name=_PERPLEXITY_MODEL,
            llm=ChatOpenAI(
                model=_PERPLEXITY_MODEL,
                api_key=settings.PERPLEXITY_API_KEY,
                base_url=_PERPLEXITY_BASE_URL,
                temperature=0.0,
            ),
        ))
        logger.info("geo_provider_enabled", provider="perplexity", model=_PERPLEXITY_MODEL)

    return providers


def build_analysis_llm() -> ChatOpenAI:
    """GPT-4o for structured per-keyword analysis.

    All provider responses are analyzed by the same model so results are
    comparable across providers. GPT-4o with strict JSON schema guarantees
    100% schema compliance.
    """
    settings = get_settings()
    return ChatOpenAI(
        model=_GPT_MODEL,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL or "https://api.openai.com/v1",
        temperature=0.0,
    )


def build_synthesis_llm() -> ChatOpenAI:
    """gpt-5.5 for strategic synthesis across all keyword results."""
    settings = get_settings()
    return ChatOpenAI(
        model=_SYNTHESIS_MODEL,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL or "https://api.openai.com/v1",
        temperature=0.0,
    )
