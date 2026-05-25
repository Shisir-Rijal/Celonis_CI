"""Typed repository helpers for the chunks table.

Provides insert and fetch operations that map between the ``Chunk`` Pydantic
model and the Supabase ``chunks`` table. All database I/O goes through these
helpers so the rest of the codebase never constructs raw Supabase queries.

Usage:
    from app.rag.repository import insert_chunk, insert_chunks, get_chunk_by_id

    chunk = Chunk(
        id=uuid4(),
        content="Celonis announced...",
        metadata=ChunkMetadata(...),
        embedding=None,
        created_at=None,
    )
    saved = insert_chunk(chunk)
    assert saved.id == chunk.id
"""

from typing import Any, cast
from uuid import UUID

from supabase import Client

from app.models.schemas import Chunk, ChunkMetadata
from app.rag.supabase_client import get_supabase

TABLE = "chunks"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _chunk_to_row(chunk: Chunk) -> dict:
    """Serialise a ``Chunk`` to a flat dict suitable for Supabase insert.

    - ``metadata`` is dumped to a plain dict (Supabase stores it as jsonb).
    - ``embedding`` is kept as ``list[float] | None``; Supabase / pgvector
      accepts a Python list and stores it as the ``vector`` column type.
    - ``id`` and ``created_at`` are serialised as strings so the JSON
      serialiser does not choke on ``UUID`` and ``datetime`` objects.
    - ``created_at=None`` is omitted so Postgres fills in ``default now()``.
    """
    row: dict = {
        "id": str(chunk.id),
        "content": chunk.content,
        "metadata": chunk.metadata.model_dump(mode="json"),
        "embedding": chunk.embedding,
    }
    if chunk.created_at is not None:
        row["created_at"] = chunk.created_at.isoformat()
    return row


def _row_to_chunk(row: dict) -> Chunk:
    """Deserialise a Supabase row dict back into a ``Chunk`` instance."""
    return Chunk(
        id=UUID(row["id"]),
        content=row["content"],
        metadata=ChunkMetadata(**row["metadata"]),
        embedding=row.get("embedding"),
        created_at=row.get("created_at"),
    )


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def insert_chunk(chunk: Chunk, *, client: Client | None = None) -> Chunk:
    """Insert a single chunk and return the persisted row as a ``Chunk``.

    Args:
        chunk: The chunk to insert. ``id`` must be set by the caller
               (use ``uuid.uuid4()``). ``created_at`` may be ``None``
               — the DB default fills it in and the returned object
               carries the persisted timestamp.
        client: Optional Supabase client override for testing. When
                ``None`` the shared module-level client is used.

    Returns:
        The persisted ``Chunk`` as returned by Supabase (includes the
        server-assigned ``created_at`` if it was not provided).

    Raises:
        Exception: Propagates any Supabase / network error unchanged.
    """
    db = client or get_supabase()
    row = _chunk_to_row(chunk)
    response = db.table(TABLE).insert(row).execute()
    return _row_to_chunk(cast(dict[str, Any], response.data[0]))


def insert_chunks(chunks: list[Chunk], *, client: Client | None = None) -> list[Chunk]:
    """Bulk-insert a list of chunks and return the persisted rows.

    Args:
        chunks: Non-empty list of ``Chunk`` objects to insert.
        client: Optional Supabase client override for testing.

    Returns:
        List of persisted ``Chunk`` objects in insertion order.

    Raises:
        ValueError: If ``chunks`` is empty (avoids a no-op DB call).
        Exception: Propagates any Supabase / network error unchanged.
    """
    if not chunks:
        raise ValueError("insert_chunks called with an empty list.")
    db = client or get_supabase()
    rows = [_chunk_to_row(c) for c in chunks]
    response = db.table(TABLE).insert(rows).execute()
    return [_row_to_chunk(cast(dict[str, Any], r)) for r in response.data]


def get_chunk_by_id(chunk_id: UUID, *, client: Client | None = None) -> Chunk | None:
    """Fetch a single chunk by its UUID primary key.

    Args:
        chunk_id: The ``UUID`` of the chunk to retrieve.
        client: Optional Supabase client override for testing.

    Returns:
        The matching ``Chunk``, or ``None`` if no row was found.

    Raises:
        Exception: Propagates any Supabase / network error unchanged.
    """
    db = client or get_supabase()
    response = (
        db.table(TABLE).select("*").eq("id", str(chunk_id)).limit(1).execute()
    )
    if not response.data:
        return None
    return _row_to_chunk(cast(dict[str, Any], response.data[0]))
