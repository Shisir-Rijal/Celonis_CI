from pydantic import BaseModel
from typing import Literal
from datetime import datetime
from uuid import UUID

class ChunkMetadata(BaseModel):
    """this class defines the metadata for a chunk of content, including information about the company, source type, date, URL, title, language, topic, content type, visual type, and chunking strategy."""
    company: str
    source_type: str
    source_origin: Literal["owned", "earned", "third_party"]
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
    Once the orchestrator is wired up (Issue #11), both will be populated
    from the real workflow output.
    """

    answer: str
    sources: list[Source] = []
