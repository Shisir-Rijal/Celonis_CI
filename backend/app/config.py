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
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource, EnvSettingsSource, DotEnvSettingsSource

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    """Process-level configuration loaded from environment variables.

    Required fields (no default) raise a ValidationError on startup when the
    variable is missing or empty. Optional fields have sensible defaults.
    """

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

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
    FINNHUB_API_KEY: str | None = None
    SERPER_API_KEY: str | None = None
    BRANDFETCH_API_KEY: str | None = None
    BRANDFETCH_CLIENT_ID: str | None = None

    # --- Backend ---
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # --- Auth ---
    APP_PASSWORD: str
    JWT_SECRET: str

    @model_validator(mode="after")
    def validate_auth_fields(self) -> "Settings":
        """Reject weak auth credentials on startup.

        JWT_SECRET under 32 chars is brute-forceable.
        APP_PASSWORD under 12 chars is trivially guessable — the login
        endpoint has no rate limiting at this stage, so a short password
        is a real attack surface.
        """
        if len(self.JWT_SECRET) < 32:
            raise ValueError(
                "JWT_SECRET must be at least 32 characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        if len(self.APP_PASSWORD) < 12:
            raise ValueError(
                "APP_PASSWORD must be at least 12 characters. "
                "The login endpoint has no rate limiting — a short password is a real risk."
            )
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        _settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        **_kwargs: object,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # .env hat Vorrang vor System-Umgebungsvariablen
        return (init_settings, dotenv_settings, env_settings)

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
