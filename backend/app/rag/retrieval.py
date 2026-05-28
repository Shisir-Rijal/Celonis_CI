"""Hybrid retrieval — vector + BM25 with metadata pre-filter and RRF fusion.

Public surface: one function.

    search_chunks(query, filters, k) -> list[Chunk]

Execution order:
  1. embed_text(query) and match_chunks_bm25 run concurrently — BM25 does
     not need the vector, so we start it immediately alongside embedding.
  2. match_chunks_vector runs once the embedding is ready.
  3. Both result lists are merged with Reciprocal Rank Fusion (k=60).
  4. Top-k chunks are returned with relevance_score set.

RRF formula (Cormack et al., 2009):
    score(chunk) = sum(1 / (60 + rank_i))  for each ranked list i
"""

import asyncio
import json
import structlog
from typing import Any, cast
from uuid import UUID

from supabase import Client

from app.models.schemas import Chunk, ChunkFilter, ChunkMetadata
from app.rag.embeddings import embed_text
from app.rag.supabase_client import get_supabase

logger = structlog.get_logger(__name__)

_RRF_K = 60
_CANDIDATE_MULTIPLIER = 3  # fetch 3× the requested k before merging


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_rpc_filter(filters: ChunkFilter) -> dict[str, Any]:
    """Serialise a ChunkFilter to the JSONB dict the RPC functions expect.

    Only non-None fields are included. The SQL functions treat a missing key
    as "no filter on this field". Datetime fields become ISO-8601 strings.
    Topic is intentionally excluded — it is applied in Python after retrieval
    (see _apply_topic_filter).
    """
    result: dict[str, Any] = {}
    if filters.company is not None:
        result["company"] = filters.company
    if filters.source_type is not None:
        result["source_type"] = filters.source_type
    if filters.source_origin is not None:
        result["source_origin"] = filters.source_origin
    if filters.date_from is not None:
        result["date_from"] = filters.date_from.isoformat()
    if filters.date_to is not None:
        result["date_to"] = filters.date_to.isoformat()
    return result


def _row_to_chunk(row: dict[str, Any]) -> Chunk:
    """Convert a raw RPC response row to a Chunk.

    pgvector/PostgREST returns the embedding column as a string
    ("[0.1,0.2,...]"). We normalise it to list[float] here.
    """
    raw_emb = row.get("embedding")
    if isinstance(raw_emb, str):
        raw_emb = json.loads(raw_emb)

    return Chunk(
        id=UUID(row["id"]),
        content=row["content"],
        metadata=ChunkMetadata(**row["metadata"]),
        embedding=raw_emb,
        created_at=row.get("created_at"),
        context_header=row.get("context_header", ""),
        document_id=UUID(row["document_id"]) if row.get("document_id") else None,
    )


def _rrf_merge(
    vector_rows: list[dict[str, Any]],
    bm25_rows: list[dict[str, Any]],
    *,
    k: int = _RRF_K,
) -> list[tuple[str, float]]:
    """Merge two ranked lists with Reciprocal Rank Fusion.

    Args:
        vector_rows: Rows from match_chunks_vector, best-first (index 0 = rank 1).
        bm25_rows:   Rows from match_chunks_bm25, best-first.
        k:           RRF constant (default 60).

    Returns:
        (chunk_id, rrf_score) pairs sorted by score descending.
        A chunk in both lists accumulates contributions from both.
    """
    scores: dict[str, float] = {}
    for rank, row in enumerate(vector_rows, start=1):
        cid = row["id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    for rank, row in enumerate(bm25_rows, start=1):
        cid = row["id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def _apply_topic_filter(chunks: list[Chunk], topics: list[str]) -> list[Chunk]:
    """Keep only chunks whose metadata.topic overlaps with the requested topics.

    Postgres array-containment on JSONB needs a specialised query pattern;
    for the small candidate sets after RRF it is simpler and equally correct
    to filter in Python.
    """
    topic_set = set(topics)
    return [c for c in chunks if topic_set.intersection(c.metadata.topic)]


def _sync_vector_search(
    db: Client,
    query_vector: list[float],
    rpc_filter: dict[str, Any],
    candidate_count: int,
) -> list[dict[str, Any]]:
    """Synchronous pgvector RPC call (run via asyncio.to_thread)."""
    resp = db.rpc(
        "match_chunks_vector",
        {
            "query_embedding": query_vector,
            "match_count": candidate_count,
            "filter": rpc_filter,
        },
    ).execute()
    return cast(list[dict[str, Any]], resp.data or [])


def _sync_bm25_search(
    db: Client,
    query: str,
    rpc_filter: dict[str, Any],
    candidate_count: int,
) -> list[dict[str, Any]]:
    """Synchronous tsvector RPC call (run via asyncio.to_thread)."""
    resp = db.rpc(
        "match_chunks_bm25",
        {
            "query_text": query,
            "match_count": candidate_count,
            "filter": rpc_filter,
        },
    ).execute()
    return cast(list[dict[str, Any]], resp.data or [])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def search_chunks(
    query: str,
    filters: ChunkFilter | None = None,
    *,
    k: int = 10,
    db_client: Client | None = None,
) -> list[Chunk]:
    """Hybrid chunk retrieval: vector + BM25 merged with RRF.

    Execution:
      - embed_text(query) and BM25 search run concurrently (BM25 needs no
        vector).
      - Vector search runs once the embedding is ready.
      - Results are merged with RRF and the top k chunks are returned.

    Args:
        query:     Natural-language query string.
        filters:   Metadata pre-filter. None = no filtering (all chunks
                   are candidates).
        k:         Maximum number of chunks to return (default 10).
        db_client: Supabase client override for testing.

    Returns:
        Up to k Chunk objects sorted by relevance descending, each with
        ``relevance_score`` set to its RRF score.

    Raises:
        EmbeddingError: If query embedding fails after all retries.
        Exception:      Propagates any Supabase RPC error unchanged.
    """
    if filters is None:
        filters = ChunkFilter()

    db = db_client or get_supabase()
    rpc_filter = _build_rpc_filter(filters)
    candidate_count = k * _CANDIDATE_MULTIPLIER

    # ------------------------------------------------------------------
    # Phase 1 — embed query and run BM25 concurrently.
    # BM25 only needs the raw query string, so it can start immediately
    # while the OpenAI embedding call is in flight.
    # ------------------------------------------------------------------
    query_vector, bm25_rows = await asyncio.gather(
        embed_text(query),
        asyncio.to_thread(_sync_bm25_search, db, query, rpc_filter, candidate_count),
    )

    # ------------------------------------------------------------------
    # Phase 2 — vector search (needs the embedding from phase 1).
    # ------------------------------------------------------------------
    vector_rows = await asyncio.to_thread(
        _sync_vector_search, db, query_vector, rpc_filter, candidate_count
    )

    logger.info(
        "retrieval_raw",
        query=query[:80],
        vector_hits=len(vector_rows),
        bm25_hits=len(bm25_rows),
    )

    # ------------------------------------------------------------------
    # Phase 3 — RRF merge + reconstruct Chunk objects.
    # ------------------------------------------------------------------
    ranked = _rrf_merge(vector_rows, bm25_rows)

    row_by_id: dict[str, dict[str, Any]] = {}
    for row in vector_rows:
        row_by_id[row["id"]] = row
    for row in bm25_rows:
        row_by_id.setdefault(row["id"], row)

    merged: list[Chunk] = []
    for chunk_id, rrf_score in ranked[:k]:
        candidate = row_by_id.get(chunk_id)
        if candidate is None:
            continue
        chunk = _row_to_chunk(candidate)
        chunk.relevance_score = rrf_score
        merged.append(chunk)

    # ------------------------------------------------------------------
    # Phase 4 — topic post-filter (Python-side, see _apply_topic_filter).
    # ------------------------------------------------------------------
    if filters.topic:
        merged = _apply_topic_filter(merged, filters.topic)

    logger.info(
        "retrieval_final",
        query=query[:80],
        returned=len(merged),
        top_score=merged[0].relevance_score if merged else None,
    )

    return merged
