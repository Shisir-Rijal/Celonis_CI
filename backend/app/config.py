"""Global settings for the Celonis CI backend.

All environment variables are loaded once on first access via
`get_settings()` and cached for the lifetime of the process. Every module
that needs a config value should call `get_settings()` rather than reading
`os.environ` directly.

Usage:
    from app.config import get_settings

    settings = get_settings()
    print(settings.OPENAI_API_KEY)
"""

from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-level configuration loaded from environment variables.

    Required fields (no default) raise a ValidationError on startup when the
    variable is missing or empty. Optional fields have sensible defaults.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM: OpenAI ---
    OPENAI_API_KEY: str
    OPENAI_BASE_URL: str | None = None
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_TEMPERATURE: float = 0.0
    OPENAI_TIMEOUT: int = 60

    # --- LLM: Anthropic + Perplexity (optional, Phase 2) ---
    ANTHROPIC_API_KEY: str | None = None
    PERPLEXITY_API_KEY: str | None = None

    # --- Supabase ---
    SUPABASE_URL: str | None = None
    SUPABASE_ANON_KEY: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None

    # --- Redis (ARQ task queue) ---
    REDIS_URL: str | None = None

    # --- Web scraping ---
    FIRECRAWL_API_KEY: str | None = None

    # --- Backend ---
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    @field_validator("OPENAI_BASE_URL", mode="before")
    @classmethod
    def normalise_base_url(cls, v: Any) -> str | None:
        """Convert empty strings and whitespace-only values to None.

        pydantic-settings parses .env values that look empty (e.g.
        'OPENAI_BASE_URL=') as an empty string, not None. AsyncOpenAI
        rejects empty strings as invalid URLs.
        """
        if v is None:
            return None
        stripped = str(v).strip()
        return stripped if stripped else None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-level Settings instance.

    Built once on first call and reused for the lifetime of the process.
    In tests, call `get_settings.cache_clear()` before overriding with a
    custom Settings instance.
    """
    return Settings()
