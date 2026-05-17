"""Shared retry logic for LLM provider calls.

One decorator, reused by every concrete client. Retries transient errors
(rate limit, timeout, connection drop) with exponential backoff. Permanent
errors (authentication, invalid request) raise immediately without retry —
no point trying again when the API key is wrong.

After all retries are exhausted, the OpenAI SDK exception is mapped to the
project's own exception class so callers never see raw provider exceptions.

Usage:
    from app.exceptions import LLMProviderError
    from app.llm.retry import with_retry

    @with_retry(error_cls=LLMProviderError)
    async def call_api():
        return await openai_client.chat.completions.create(...)
"""

import structlog
from functools import wraps
from typing import Callable, Type

from openai import RateLimitError, APITimeoutError, APIConnectionError
from tenacity import (
    AsyncRetrying,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)

from app.exceptions import (
    AppError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)

logger = structlog.get_logger(__name__)


# Transient errors — worth retrying because they often resolve on their own.
_TRANSIENT_ERRORS = (RateLimitError, APITimeoutError, APIConnectionError)


def _map_exception(exc: Exception, fallback_cls: Type[AppError]) -> AppError:
    """Convert an OpenAI SDK exception into the project's own exception type.

    Specific OpenAI exceptions map to specific project exceptions where it
    matters (rate limit, timeout). Everything else falls back to the caller's
    chosen class (e.g. LLMProviderError for chat, EmbeddingError for embeddings).
    """
    if isinstance(exc, RateLimitError):
        return LLMRateLimitError(f"Rate limit reached: {exc}")
    if isinstance(exc, APITimeoutError):
        return LLMTimeoutError(f"Request timed out: {exc}")
    return fallback_cls(f"Provider call failed: {exc}")


def with_retry(error_cls: Type[AppError] = LLMProviderError) -> Callable:
    """Decorator factory: wraps an async function with retry + exception mapping.

    Retry policy:
        - Maximum 3 attempts (1 original + 2 retries)
        - Exponential backoff: 2s, then 4s, then 8s
        - Only retries on transient errors (rate limit, timeout, connection)
        - Authentication / invalid request errors raise immediately

    Args:
        error_cls: Project exception class to raise when retries are exhausted
            or a non-transient error occurs. Defaults to LLMProviderError;
            embedding callers should pass EmbeddingError.

    Returns:
        A decorator that wraps an async function.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                async for attempt in AsyncRetrying(
                    retry=retry_if_exception_type(_TRANSIENT_ERRORS),
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=1, min=2, max=10),
                    reraise=True,
                ):
                    with attempt:
                        if attempt.retry_state.attempt_number > 1:
                            logger.warning(
                                "llm_retry",
                                attempt=attempt.retry_state.attempt_number,
                                function=func.__name__,
                            )
                        return await func(*args, **kwargs)
            except _TRANSIENT_ERRORS as exc:
                # Retries exhausted — map and raise our own exception.
                logger.error(
                    "llm_retries_exhausted",
                    function=func.__name__,
                    error=str(exc),
                )
                raise _map_exception(exc, error_cls) from exc
            except RetryError as exc:
                # Tenacity wrapped the final exception.
                last = exc.last_attempt.exception() if exc.last_attempt else exc
                raise _map_exception(last, error_cls) from exc
            except Exception as exc:
                # Permanent error (auth, invalid request, etc.) — no retry.
                logger.error(
                    "llm_call_failed",
                    function=func.__name__,
                    error=str(exc),
                )
                raise _map_exception(exc, error_cls) from exc

        return wrapper
    return decorator
