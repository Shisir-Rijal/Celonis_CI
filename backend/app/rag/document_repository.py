"""Repository helpers for the documents table.

The documents table is the parent layer above chunks — one document is
fetched once and can produce N chunks. This module owns all CRUD for that
table and exposes one read-only helper that crosses into the chunks table
(get_chunk_ids_by_document) purely for the deduplication return path in
the ingestion pipeline.

All functions follow the same pattern as repository.py:
  - optional ``client`` param for test injection
  - raw Supabase calls stay inside this file
  - callers work with plain dicts or typed values, never postgrest internals
"""

import hashlib
from typing import Any, cast
from uuid import UUID

from supabase import Client

from app.rag.supabase_client import get_supabase

DOCUMENTS_TABLE = "documents"
CHUNKS_TABLE = "chunks"


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def compute_content_hash(text: str) -> str:
    """Return the SHA-256 hex digest of the raw document text.

    Used for deduplication: if a document with the same hash already exists
    in the documents table we skip re-ingestion entirely. The hash is
    computed over the raw text, not over chunks, so it is stable regardless
    of chunking strategy changes.
    """
    return hashlib.sha256(text.encode()).hexdigest()


# ---------------------------------------------------------------------------
# documents table
# ---------------------------------------------------------------------------

def get_document_by_hash(
    content_hash: str,
    *,
    client: Client | None = None,
) -> dict | None:
    """Look up a document by its content hash.

    Returns the full row dict if found, or None if this document has never
    been ingested. The pipeline uses this to short-circuit on duplicate
    content before doing any embedding work.
    """
    db = client or get_supabase()
    resp = (
        db.table(DOCUMENTS_TABLE)
        .select("*")
        .eq("content_hash", content_hash)
        .limit(1)
        .execute()
    )
    return cast(dict[str, Any], resp.data[0]) if resp.data else None


def create_document(
    *,
    url: str,
    content_hash: str,
    raw_content: str,
    source_type: str,
    company: str,
    client: Client | None = None,
) -> dict:
    """Insert a new document record and return the created row.

    The row starts with ingestion_status='pending'. The pipeline updates
    this to 'done' or 'error' once it finishes.
    """
    db = client or get_supabase()
    resp = (
        db.table(DOCUMENTS_TABLE)
        .insert({
            "url": url,
            "content_hash": content_hash,
            "raw_content": raw_content,
            "source_type": source_type,
            "company": company,
            "ingestion_status": "pending",
        })
        .execute()
    )
    return cast(dict[str, Any], resp.data[0])


def update_document_status(
    document_id: UUID,
    status: str,
    error_detail: str | None = None,
    *,
    client: Client | None = None,
) -> None:
    """Update the lifecycle status of a document.

    Valid transitions the pipeline uses:
      pending  → done   (happy path — all chunks embedded and persisted)
      pending  → error  (something failed — error_detail carries the message)

    Does not validate the status value here — the DB CHECK constraint
    ('pending', 'chunked', 'embedded', 'done', 'error') enforces it.
    """
    db = client or get_supabase()
    payload: dict = {"ingestion_status": status}
    if error_detail is not None:
        payload["error_detail"] = error_detail
    (
        db.table(DOCUMENTS_TABLE)
        .update(payload)
        .eq("id", str(document_id))
        .execute()
    )


# ---------------------------------------------------------------------------
# Cross-table read (deduplication return path only)
# ---------------------------------------------------------------------------

def get_chunk_ids_by_document(
    document_id: UUID,
    *,
    client: Client | None = None,
) -> list[UUID]:
    """Return the UUIDs of all chunks belonging to a document.

    Read-only. Used only when a document is already 'done' and the pipeline
    needs to return existing chunk UUIDs instead of re-embedding. No chunk
    is created or modified here.
    """
    db = client or get_supabase()
    resp = (
        db.table(CHUNKS_TABLE)
        .select("id")
        .eq("document_id", str(document_id))
        .execute()
    )
    return [UUID(cast(dict[str, Any], row)["id"]) for row in resp.data]
