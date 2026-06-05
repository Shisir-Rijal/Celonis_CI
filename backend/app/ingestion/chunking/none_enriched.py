"""
No-enrichment chunking strategy for short content.

No splitting is applied —> full text becomes one chunk. A context-header
derived from the chunk metadata is addded to the beginning of the chunk content 
before embedding so the model has structured context even for very short texts.

Header enrichment:
The header is only added in the none_enriched strategy because short-form content
lacks context for the embedding model. Structural and agentic chunks are large enough 
to carry their own context, and adding the same header to every chunk would 
waste tokens redundantly.

Header format: "Company: X | Type: Y | Date: YYYY-MM-DD | Title: T"
If title is absent the Title field is omitted from the header.
"""
import uuid
from datetime import datetime, timezone

from app.ingestion.chunking._utils import build_context_header
from app.models.schemas import Chunk, ChunkMetadata


def chunk_none_enriched(text: str, metadata: ChunkMetadata) -> list[Chunk]:
    """Return the full text as a single chunk with a context header prepended."""
    header = build_context_header(metadata)
    enriched_content = f"{header}\n\n{text}"

    chunk_meta = metadata.model_copy(update={"chunking_strategy": "none"})

    return [
        Chunk(
            id=uuid.uuid4(),
            content=enriched_content,
            metadata=chunk_meta,
            embedding=None,
            created_at=datetime.now(timezone.utc),
        )
    ]
