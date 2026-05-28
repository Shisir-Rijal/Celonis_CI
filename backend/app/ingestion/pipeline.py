"""Ingestion pipeline — single entry point for bringing a document into the RAG corpus.

``ingest_document`` is the public surface of this module. It ties together:
  - Content-hash deduplication (documents table)
  - Document lifecycle tracking (pending → done | error)
  - Chunking (injected from caller until Issue #8 is ready)
  - Contextual embedding via embed_chunks
  - Bulk insert into the chunks table

Callers (ingestion connectors, tests, manual backfill scripts) should only
ever call ``ingest_document``. The helper modules it depends on
(document_repository, repository, embeddings) are implementation details.

Fallback chunking:
  Until Issue #8 (Chunking Dispatcher) is merged, ``ingest_document`` accepts
  an optional ``chunks`` parameter. When ``chunks`` is None it falls back to a
  single-chunk strategy: the entire raw text becomes one chunk with a minimal
  context header derived from the metadata. This keeps the pipeline runnable
  before the real chunker exists. Once Issue #8 is wired in, callers will
  always pass pre-built chunks and the fallback path will be dead code.
"""

import structlog
import structlog.contextvars
from uuid import UUID, uuid4

from supabase import Client

from app.models.schemas import Chunk, ChunkMetadata
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
    url: str,
    source_type: str,
    company: str,
    *,
    chunks: list[Chunk] | None = None,
    db_client: Client | None = None,
) -> list[UUID]:
    """Ingest a document into the RAG corpus and return the chunk UUIDs.

    This is the main entry point for the ingestion pipeline. It deduplicates,
    tracks document lifecycle, embeds, and persists — in that order.

    Args:
        text:        Raw document text (used for hashing and fallback chunking).
        metadata:    Chunk-level metadata applied to every chunk of this document.
        url:         Canonical URL of the source. Used for deduplication lookup
                     and stored on the document record.
        source_type: E.g. ``"news"``, ``"press_release"``, ``"earnings_call"``.
                     Stored on the document record; the chunking dispatcher in
                     Issue #8 will also use this to pick a strategy.
        company:     Company the document is about (e.g. ``"celonis"``).
        chunks:      Pre-built Chunk objects from the chunking dispatcher (Issue
                     #8). When ``None``, a single-chunk fallback is used so the
                     pipeline stays runnable before the real chunker exists.
                     Every chunk MUST have ``context_header`` set by the caller.
        db_client:   Optional Supabase client override for testing.

    Returns:
        List of UUID of the persisted chunks. If the document was already
        ingested (content hash found, status ``done``) the existing chunk UUIDs
        are returned immediately without any re-embedding.

    Raises:
        ValueError: If any supplied chunk has an empty ``context_header`` — the
            caller (chunker) is responsible for setting headers before calling
            this function.
        Exception:  Any embedding or DB error is propagated after updating the
            document status to ``"error"``.
    """
    # ------------------------------------------------------------------
    # 0. Bind a correlation ID so every log event in this call is linked.
    #    structlog.contextvars carries it automatically to all loggers in scope.
    # ------------------------------------------------------------------
    correlation_id = str(uuid4())
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    # ------------------------------------------------------------------
    # 1. Deduplication / retry detection
    # The documents table has UNIQUE(content_hash). We must never call
    # create_document when a row for this hash already exists — even if
    # the previous run failed — or we hit a Unique-Violation.
    # ------------------------------------------------------------------
    content_hash = compute_content_hash(text)
    existing = get_document_by_hash(content_hash, client=db_client)

    if existing:
        if existing.get("ingestion_status") == "done":
            # Already fully ingested — short-circuit, no re-embedding.
            document_id = UUID(existing["id"])
            logger.info(
                "document_already_ingested",
                url=url,
                document_id=str(document_id),
            )
            return get_chunk_ids_by_document(document_id, client=db_client)
        else:
            # Previous run is pending or errored — re-use the existing record
            # and reset its status so the retry path is clean.
            document_id = UUID(existing["id"])
            update_document_status(document_id, "pending", client=db_client)
            logger.info(
                "document_retry",
                url=url,
                document_id=str(document_id),
                previous_status=existing.get("ingestion_status"),
            )
    else:
        # ------------------------------------------------------------------
        # 2. Brand-new document — create the record (status = "pending")
        # ------------------------------------------------------------------
        doc = create_document(
            url=url,
            content_hash=content_hash,
            raw_content=text,
            source_type=source_type,
            company=company,
            client=db_client,
        )
        document_id = UUID(doc["id"])
        logger.info("document_created", url=url, document_id=str(document_id))

    try:
        # ------------------------------------------------------------------
        # 3. Chunking
        # Issue #8 will always supply chunks from the dispatcher. Until then,
        # fall back to a single chunk with a minimal metadata-derived header.
        # ------------------------------------------------------------------
        if chunks is None:
            fallback_header = (
                f"{metadata.source_type} | {metadata.company} | "
                f"{metadata.date.date()}"
            )
            chunks = [
                Chunk(
                    id=uuid4(),
                    content=text,
                    metadata=metadata,
                    embedding=None,
                    created_at=None,
                    context_header=fallback_header,
                )
            ]
            logger.debug(
                "fallback_chunking_used",
                document_id=str(document_id),
                note="Replace with Issue #8 chunking dispatcher",
            )

        # ------------------------------------------------------------------
        # 4. Stamp each chunk with the document FK
        # ------------------------------------------------------------------
        for chunk in chunks:
            chunk.document_id = document_id

        # ------------------------------------------------------------------
        # 5. Embed — raises ValueError if any chunk has an empty context_header
        # ------------------------------------------------------------------
        chunks = await embed_chunks(chunks)

        # ------------------------------------------------------------------
        # 6. Persist
        # ------------------------------------------------------------------
        insert_chunks(chunks, client=db_client)

        # ------------------------------------------------------------------
        # 7. Mark document as done
        # ------------------------------------------------------------------
        update_document_status(document_id, "done", client=db_client)
        logger.info(
            "document_ingested",
            url=url,
            document_id=str(document_id),
            num_chunks=len(chunks),
        )

        return [c.id for c in chunks]

    except Exception as exc:
        # Best-effort status update — if the DB is also down this will fail
        # silently, which is acceptable (the document stays "pending" and
        # can be retried).
        try:
            update_document_status(
                document_id,
                "error",
                error_detail=str(exc),
                client=db_client,
            )
        except Exception:
            pass
        raise
    finally:
        structlog.contextvars.unbind_contextvars("correlation_id")
