"""Global exception hierarchy for the Celonis CI backend.

All custom exceptions inherit from AppError so callers can catch either
a specific error or the base class depending on how much granularity they need.

Usage:
    from app.exceptions import LLMProviderError, RetryableError

    raise LLMProviderError("Model unavailable") from original_exception
"""


class AppError(Exception):
    """Base class for all application-level exceptions.

    Catching AppError catches every custom exception in this module.
    Never raise AppError directly — always raise a specific subclass.
    """


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

class LLMProviderError(AppError):
    """Raised when an LLM provider call fails after all retries are exhausted.

    Callers should surface this as a 503 Service Unavailable.
    """


class LLMRateLimitError(LLMProviderError):
    """Raised when the provider returns a rate-limit response (429).

    Subclass of LLMProviderError so it can be caught broadly or specifically.
    """


class LLMTimeoutError(LLMProviderError):
    """Raised when an LLM call exceeds the configured timeout."""


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

class EmbeddingError(AppError):
    """Raised when generating embeddings fails after all retries."""


# ---------------------------------------------------------------------------
# Retrieval / RAG
# ---------------------------------------------------------------------------

class RetrievalError(AppError):
    """Raised when a vector or keyword search query fails."""


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

class IngestionError(AppError):
    """Raised when a document cannot be chunked, embedded, or stored."""


class ChunkingError(IngestionError):
    """Raised when a chunking strategy fails to process a document."""


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class SupabaseError(AppError):
    """Raised when a Supabase read or write operation fails."""

class RepositoryError(SupabaseError):
    """Raised when a repository-level database operation fails."""

class AssessmentError(AppError):
    """Raised when the Assessment node cannot parse or validate the LLM response."""

class CapabilityRegistrationError(AppError):
    """Raised when a capability name is registered more than once."""

class SynthesisError(AppError):
    """Raised when the Synthesize node cannot parse the LLM response."""

# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

class NewsError(AppError):
    """Raised when all news sources fail and no articles could be fetched."""