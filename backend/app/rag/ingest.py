"""backend/app/rag/ingest.py

ingest_document() — single entry point for adding content to the RAG corpus.

Takes raw text + ChunkMetadata, splits it via the chunking dispatcher,
embeds, and persists to Supabase.

Used by:
  - Any future ingestion pipeline that has text + metadata

Never called from orchestrator nodes directly.

Flow:
  1. Compute content hash → skip if already ingested (deduplication)
  2. Create document row (status=pending)
  3. Chunk via dispatcher (strategy determined by source_type in metadata)
  4. Set document_id on each chunk
  5. Embed all chunks in batches
  6. Persist chunks to Supabase
  7. Mark document as done
"""

from uuid import UUID

import structlog

from app.ingestion.chunking.dispatcher import chunk as chunk_document
from app.llm.base import ChatClient
from app.models.schemas import ChunkMetadata
from app.rag.document_repository import (
    compute_content_hash,
    create_document,
    get_chunk_ids_by_document,
    get_document_by_hash,
    update_document_status,
)
from app.rag.embeddings import embed_chunks
from app.rag.repository import insert_chunks

logger = structlog.get_logger(__name__)


async def ingest_document(
    text: str,
    metadata: ChunkMetadata,
    client: ChatClient | None = None,
) -> list[UUID]:
    """Ingest a single document into the RAG corpus.

    Idempotent: if a document with the same content hash already exists
    and is marked 'done', returns the existing chunk UUIDs without
    re-embedding or re-inserting anything.

    Args:
        text:     Raw document text. Must be non-empty.
        metadata: ChunkMetadata applied to every chunk from this document.
                  Chunking strategy is derived from metadata.source_type
                  by the dispatcher — not from chunking_strategy directly.
        client:   LLM client required for agentic chunking (earnings calls,
                  analyst reports). Ignored for structural and none strategies.

    Returns:
        List of chunk UUIDs that are now in the corpus (new or existing).

    Raises:
        ValueError:     If text is empty.
        ChunkingError:  If agentic chunking is needed but no client provided.
        EmbeddingError: If the embedding call fails after retries.
        Exception:      Any Supabase error propagates unchanged.
    """
    if not text.strip():
        raise ValueError("ingest_document: text must be non-empty.")

    log = logger.bind(
        company=metadata.company,
        url=metadata.url,
        source_type=metadata.source_type,
    )

    # 1 — Deduplication: same content hash means same document
    content_hash = compute_content_hash(text)
    existing = get_document_by_hash(content_hash)
    if existing and existing.get("ingestion_status") == "done":
        log.info("document_already_ingested", document_id=existing["id"])
        return get_chunk_ids_by_document(UUID(existing["id"]))

    # 2 — Create document record (status = pending)
    doc = create_document(
        url=metadata.url,
        content_hash=content_hash,
        raw_content=text,
        source_type=metadata.source_type,
        company=metadata.company,
    )
    document_id = UUID(doc["id"])
    log = log.bind(document_id=str(document_id))

    try:
        # 3 — Chunk via dispatcher (routes by source_type)
        chunks = await chunk_document(text, metadata, client=client)
        log.info("document_split", chunk_count=len(chunks))

        # 4 — Attach document_id to each chunk
        chunks = [c.model_copy(update={"document_id": document_id}) for c in chunks]

        # 5 — Embed (mutates chunk.embedding in place, batched at 100)
        await embed_chunks(chunks)

        # 6 — Persist to Supabase
        persisted = insert_chunks(chunks)
        log.info("document_ingested", chunk_count=len(persisted))

        # 7 — Mark done
        update_document_status(document_id, "done")

        return [c.id for c in persisted]

    except Exception as exc:
        update_document_status(document_id, "error", error_detail=str(exc))
        log.error("document_ingestion_failed", error=str(exc))
        raise
