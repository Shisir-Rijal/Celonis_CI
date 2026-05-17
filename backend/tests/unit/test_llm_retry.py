"""Unit tests for app/llm/retry.py and exception mapping.

No real API calls — all OpenAI responses are mocked. Tests verify:
- Transient errors are retried up to 3 times
- Permanent errors raise immediately without retry
- OpenAI exceptions are mapped to the project's own exception classes
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from openai import RateLimitError, APITimeoutError, AuthenticationError

from app.exceptions import (
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    EmbeddingError,
)
from app.llm.retry import with_retry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_rate_limit_error() -> RateLimitError:
    """Build a minimal RateLimitError that matches the openai SDK structure."""
    response = MagicMock()
    response.status_code = 429
    response.headers = {}
    return RateLimitError("rate limit", response=response, body={})


def make_timeout_error() -> APITimeoutError:
    return APITimeoutError(request=MagicMock())


def make_auth_error() -> AuthenticationError:
    response = MagicMock()
    response.status_code = 401
    response.headers = {}
    return AuthenticationError("invalid key", response=response, body={})


# ---------------------------------------------------------------------------
# Retry behaviour
# ---------------------------------------------------------------------------

class TestRetryBehaviour:
    async def test_succeeds_on_first_attempt(self):
        """No retry needed when the call succeeds immediately."""
        call_count = 0

        @with_retry(error_cls=LLMProviderError)
        async def fn():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await fn()
        assert result == "ok"
        assert call_count == 1

    async def test_retries_on_rate_limit_then_succeeds(self):
        """Fails once with RateLimitError, succeeds on second attempt."""
        call_count = 0

        @with_retry(error_cls=LLMProviderError)
        async def fn():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise make_rate_limit_error()
            return "ok"

        # Patch tenacity wait so the test doesn't actually sleep.
        with patch("app.llm.retry.wait_exponential", return_value=lambda _: 0):
            result = await fn()

        assert result == "ok"
        assert call_count == 2

    async def test_raises_after_three_failed_attempts(self):
        """All 3 attempts fail — should raise LLMProviderError, not RateLimitError."""
        call_count = 0

        @with_retry(error_cls=LLMProviderError)
        async def fn():
            nonlocal call_count
            call_count += 1
            raise make_rate_limit_error()

        with patch("app.llm.retry.wait_exponential", return_value=lambda _: 0):
            with pytest.raises(LLMProviderError):
                await fn()

        assert call_count == 3

    async def test_no_retry_on_permanent_error(self):
        """AuthenticationError is not retryable — should raise immediately."""
        call_count = 0

        @with_retry(error_cls=LLMProviderError)
        async def fn():
            nonlocal call_count
            call_count += 1
            raise make_auth_error()

        with pytest.raises(LLMProviderError):
            await fn()

        assert call_count == 1


# ---------------------------------------------------------------------------
# Exception mapping
# ---------------------------------------------------------------------------

class TestExceptionMapping:
    async def test_rate_limit_maps_to_llm_rate_limit_error(self):
        @with_retry(error_cls=LLMProviderError)
        async def fn():
            raise make_rate_limit_error()

        with patch("app.llm.retry.wait_exponential", return_value=lambda _: 0):
            with pytest.raises(LLMRateLimitError):
                await fn()

    async def test_timeout_maps_to_llm_timeout_error(self):
        @with_retry(error_cls=LLMProviderError)
        async def fn():
            raise make_timeout_error()

        with patch("app.llm.retry.wait_exponential", return_value=lambda _: 0):
            with pytest.raises(LLMTimeoutError):
                await fn()

    async def test_embedding_errors_use_embedding_error_class(self):
        """When error_cls=EmbeddingError, unknown errors fall back to that class.

        Note: specific OpenAI errors (RateLimitError, APITimeoutError) always
        map to their own project exception type (LLMRateLimitError, LLMTimeoutError)
        regardless of error_cls. error_cls is the fallback for everything else.
        """
        @with_retry(error_cls=EmbeddingError)
        async def fn():
            raise ValueError("unexpected embedding format")  # not an OpenAI exception

        with pytest.raises(EmbeddingError):
            await fn()

    async def test_raw_openai_exception_never_escapes(self):
        """Callers must never see a raw OpenAI exception — always mapped."""
        @with_retry(error_cls=LLMProviderError)
        async def fn():
            raise make_rate_limit_error()

        with patch("app.llm.retry.wait_exponential", return_value=lambda _: 0):
            with pytest.raises(LLMProviderError):
                await fn()

        # Verify it's NOT the raw OpenAI type.
        with patch("app.llm.retry.wait_exponential", return_value=lambda _: 0):
            try:
                await fn()
            except LLMProviderError:
                pass
            except RateLimitError:
                pytest.fail("Raw OpenAI RateLimitError escaped the retry decorator")
