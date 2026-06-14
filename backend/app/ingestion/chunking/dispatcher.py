"""
Dispatcher: routes text to the correct chunking strategy.

The caller sets metadata.chunking_strategy explicitly — the dispatcher
reads it and calls the right function. source_type plays no role here.

Guidance for callers (what strategy fits what content):
  "structural"  — Markdown-based content with headings: news, press releases,
                  websites, career pages, blog posts
  "none"        — Short-form content without structure: social posts,
                  GEO/AI-search responses, Reddit threads
  "agentic"     — Long-form premium documents where semantic sections matter:
                  earnings calls, analyst reports (requires client=)
"""

from app.exceptions import ChunkingError
from app.llm.base import ChatClient
from app.models.schemas import Chunk, ChunkMetadata

from app.ingestion.chunking.structural import chunk_structural
from app.ingestion.chunking.none_enriched import chunk_none_enriched
from app.ingestion.chunking.agentic import chunk_agentic


async def chunk(
    text: str,
    metadata: ChunkMetadata,
    client: ChatClient | None = None,
) -> list[Chunk]:
    """Route text to the correct chunking strategy based on metadata.chunking_strategy."""
    strategy = metadata.chunking_strategy

    if strategy == "none":
        return chunk_none_enriched(text, metadata)

    if strategy == "agentic":
        if client is None:
            raise ChunkingError(
                "chunking_strategy='agentic' requires a ChatClient. "
                "Pass client= to ingest_document()."
            )
        return await chunk_agentic(text, metadata, client)

    return chunk_structural(text, metadata)  # "structural" + any unknown value
