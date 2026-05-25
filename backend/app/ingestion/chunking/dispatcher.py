"""
Dispatcher logic:
The dispatcher selects a strategy based on source_type, not text length.
Source_type tells us not just how long a document typically is, but how it's structured
and what split quality is needed. Character or token count is not a factor.
"""

from app.exceptions import ChunkingError
from app.llm.base import ChatClient  # app/llm/base.py —> needed for agentic strategy
from app.models.schemas import Chunk, ChunkMetadata  # app/models/schemas.py —> shared data models

from app.ingestion.chunking.structural import chunk_structural
from app.ingestion.chunking.none_enriched import chunk_none_enriched
from app.ingestion.chunking.agentic import chunk_agentic

# Maps each source_type to its chunking strategy
_STRUCTURAL_TYPES = {"press_release", "news", "website", "career_page"}
_NONE_ENRICHED_TYPES = {"social", "geo_response", "reddit"}
_AGENTIC_TYPES = {"earnings_call", "analyst_report"}


async def chunk(
    text: str,
    metadata: ChunkMetadata,
    client: ChatClient | None = None,
) -> list[Chunk]:
    source_type = metadata.source_type

    if source_type in _NONE_ENRICHED_TYPES:
        return chunk_none_enriched(text, metadata)

    if source_type in _AGENTIC_TYPES:
        if client is None:
            raise ChunkingError(
                f"source_type '{source_type}' requires agentic chunking but no ChatClient was provided."
            )
        return await chunk_agentic(text, metadata, client)

    # default: structural (covers _STRUCTURAL_TYPES and any unknown source_type)
    return chunk_structural(text, metadata)
