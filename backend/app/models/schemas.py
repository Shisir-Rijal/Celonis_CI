from pydantic import BaseModel
from typing import Literal
from datetime import datetime
from uuid import UUID

class ChunkMetadata(BaseModel):
    """this class defines the metadata for a chunk of content, including information about the company, source type, date, URL, title, language, topic, content type, visual type, and chunking strategy."""
    company: str
    source_type: str
    source_origin: Literal["owned", "earned", "third_party", "internal"]
    date: datetime
    url: str
    title: str | None
    language: str
    topic: list[str]
    content_type: Literal["text", "image", "transcript"]
    visual_type: str | None
    chunking_strategy: Literal["structural", "none", "agentic"]

class Chunk(BaseModel):
    """this class defines a chunk of content, including its unique identifier, the content itself, its metadata, an optional embedding vector, and the date it was created."""
    id: UUID
    content: str
    metadata: ChunkMetadata
    embedding: list[float] | None
    created_at: datetime | None


# ---------------------------------------------------------------------------
# Chat API models
# ---------------------------------------------------------------------------

class Source(BaseModel):
    """A source reference returned alongside a chat answer.

    Carries enough information for the frontend to display a citation and
    link back to the original document.
    """

    url: str
    title: str | None = None
    relevance_score: float


class ChatRequest(BaseModel):
    """Incoming body for POST /chat."""

    query: str


class ChatResponse(BaseModel):
    """Response body for POST /chat.

    In the stub phase `answer` is a fixed string and `sources` is empty.
    Once the orchestrator is wired up (Issue #11), all fields will be
    populated from the real workflow output.

    ``derivation`` carries the LLM's step-by-step reasoning so the UI can
    show *how* the answer was reached (Anthropic analytical derivation
    pattern). Empty string during the stub phase; never None so the
    frontend can always render it without a null guard.
    """

    answer: str
    sources: list[Source] = []
    derivation: str = ""


# ---------------------------------------------------------------------------
# Auth API models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """Incoming body for POST /auth/login."""

    password: str


class TokenResponse(BaseModel):
    """Response body for POST /auth/login on success."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400  # 24h in seconds
