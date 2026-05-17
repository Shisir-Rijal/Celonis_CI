"""OpenAI implementation of ChatClient and EmbeddingClient.

Wraps the official `openai` Python SDK. Every API call goes through the
shared retry decorator from `app/llm/retry.py` — transient errors are
retried automatically, and all OpenAI exceptions are mapped to the
project's own exception classes before they leave this module.

Usage:
    from app.llm.openai_client import get_openai_client

    client = get_openai_client()
    text   = await client.complete([{"role": "user", "content": "Hello"}])
    vector = await client.embed(["some text"])
"""

import structlog
from functools import lru_cache

from openai import AsyncOpenAI

from app.config import Settings, get_settings
from app.exceptions import EmbeddingError, LLMProviderError
from app.llm.base import ChatClient, EmbeddingClient
from app.llm.retry import with_retry

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class OpenAIClient(ChatClient, EmbeddingClient):
    """Concrete LLM client backed by the OpenAI API.

    Implements both ChatClient and EmbeddingClient. Every public method
    has the retry decorator applied so transient errors are handled
    transparently.

    Args:
        settings: The global Settings instance. Defaults to
            ``get_settings()`` when not provided explicitly, which is the
            correct behaviour in production. Pass a custom Settings object
            in tests to avoid loading ``.env``.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = AsyncOpenAI(
            api_key=self._settings.OPENAI_API_KEY,
            base_url=self._settings.OPENAI_BASE_URL or "https://api.openai.com/v1",
            timeout=self._settings.OPENAI_TIMEOUT,
        )

    @with_retry(error_cls=LLMProviderError)
    async def complete(self, messages: list[dict], **kwargs) -> str:
        """Send messages to the OpenAI chat API and return the reply.

        Args:
            messages: List of dicts with "role" and "content" keys.
                Vision inputs are supported — pass content as a list of
                {"type": "text"} and {"type": "image_url"} parts.
            **kwargs: Overrides for model, temperature, max_tokens, etc.
                If not provided, values from settings are used.

        Returns:
            The model's reply as a plain string.

        Raises:
            LLMProviderError: If the call fails after all retries.
        """
        model = kwargs.pop("model", self._settings.OPENAI_CHAT_MODEL)
        temperature = kwargs.pop("temperature", self._settings.OPENAI_TEMPERATURE)

        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            **kwargs,
        )

        logger.info(
            "openai_complete",
            model=response.model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )

        return response.choices[0].message.content

    @with_retry(error_cls=EmbeddingError)
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts using the OpenAI Embeddings API.

        Args:
            texts: List of strings to embed. Can be a single-element list
                if only one embedding is needed.

        Returns:
            List of embedding vectors, one per input text, in the same
            order. Each vector has 1536 dimensions for text-embedding-3-small.

        Raises:
            EmbeddingError: If the call fails after all retries.
        """
        response = await self._client.embeddings.create(
            model=self._settings.OPENAI_EMBEDDING_MODEL,
            input=texts,
        )

        logger.info(
            "openai_embed",
            model=self._settings.OPENAI_EMBEDDING_MODEL,
            input_count=len(texts),
            total_tokens=response.usage.total_tokens,
        )

        # The API returns embeddings sorted by index, but we sort explicitly
        # to be safe — order must match the input list.
        sorted_data = sorted(response.data, key=lambda d: d.index)
        return [item.embedding for item in sorted_data]


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_openai_client() -> OpenAIClient:
    """Return the process-level OpenAIClient instance.

    Built once on first call and reused for the lifetime of the process.
    Call this everywhere instead of instantiating OpenAIClient directly.
    """
    logger.info("initialising_openai_client")
    return OpenAIClient()
