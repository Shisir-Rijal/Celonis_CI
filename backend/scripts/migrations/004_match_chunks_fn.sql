-- Migration 004: hybrid search RPC functions
--
-- Adds two Postgres functions callable via supabase.rpc() for hybrid
-- retrieval (vector + BM25). Both functions accept a JSONB metadata filter
-- so Postgres can apply the pre-filter inside the function — not in Python.
--
-- match_chunks_vector  — cosine similarity via pgvector (<=>)
-- match_chunks_bm25    — keyword ranking via tsvector / ts_rank_cd
--
-- Prerequisites:
--   - Migration 001 applied (chunks table, pgvector, content_tsv GIN index)
--
-- Idempotent: CREATE OR REPLACE is safe to re-run.

-- ---------------------------------------------------------------------------
-- 1. Vector search
--    Returns up to match_count rows ordered by cosine similarity (highest
--    first). Chunks without an embedding are excluded. The JSONB filter is
--    applied as SQL WHERE predicates so the query planner can use indexes.
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION match_chunks_vector(
    query_embedding vector(1536),
    match_count     int,
    filter          jsonb DEFAULT '{}'
)
RETURNS TABLE (
    id              uuid,
    content         text,
    metadata        jsonb,
    context_header  text,
    document_id     uuid,
    embedding       vector(1536),
    created_at      timestamptz,
    similarity      float
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.content,
        c.metadata,
        c.context_header,
        c.document_id,
        c.embedding,
        c.created_at,
        -- Cosine similarity: 1 − cosine distance. Range [−1, 1]; higher = more similar.
        (1 - (c.embedding <=> query_embedding))::float AS similarity
    FROM chunks c
    WHERE
        c.embedding IS NOT NULL
        -- Each predicate is a no-op when the filter key is absent (IS NULL check).
        AND (filter->>'company'       IS NULL
             OR c.metadata->>'company' = filter->>'company')
        AND (filter->>'source_type'   IS NULL
             OR c.metadata->>'source_type' = filter->>'source_type')
        AND (filter->>'source_origin' IS NULL
             OR c.metadata->>'source_origin' = filter->>'source_origin')
        AND (filter->>'date_from'     IS NULL
             OR (c.metadata->>'date')::timestamptz >= (filter->>'date_from')::timestamptz)
        AND (filter->>'date_to'       IS NULL
             OR (c.metadata->>'date')::timestamptz <= (filter->>'date_to')::timestamptz)
    ORDER BY c.embedding <=> query_embedding   -- ASC = nearest first
    LIMIT match_count;
END;
$$;


-- ---------------------------------------------------------------------------
-- 2. BM25 keyword search
--    Uses the pre-computed tsvector column (content_tsv, GIN-indexed in
--    migration 001) and ts_rank_cd for scoring. Returns rows that match the
--    query at all (the @@ operator), ordered by rank descending.
--    plainto_tsquery handles natural-language input without requiring the
--    caller to escape special characters.
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION match_chunks_bm25(
    query_text  text,
    match_count int,
    filter      jsonb DEFAULT '{}'
)
RETURNS TABLE (
    id              uuid,
    content         text,
    metadata        jsonb,
    context_header  text,
    document_id     uuid,
    embedding       vector(1536),
    created_at      timestamptz,
    bm25_rank       float
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.content,
        c.metadata,
        c.context_header,
        c.document_id,
        c.embedding,
        c.created_at,
        ts_rank_cd(c.content_tsv, plainto_tsquery('english', query_text))::float AS bm25_rank
    FROM chunks c
    WHERE
        c.content_tsv @@ plainto_tsquery('english', query_text)
        AND (filter->>'company'       IS NULL
             OR c.metadata->>'company' = filter->>'company')
        AND (filter->>'source_type'   IS NULL
             OR c.metadata->>'source_type' = filter->>'source_type')
        AND (filter->>'source_origin' IS NULL
             OR c.metadata->>'source_origin' = filter->>'source_origin')
        AND (filter->>'date_from'     IS NULL
             OR (c.metadata->>'date')::timestamptz >= (filter->>'date_from')::timestamptz)
        AND (filter->>'date_to'       IS NULL
             OR (c.metadata->>'date')::timestamptz <= (filter->>'date_to')::timestamptz)
    ORDER BY bm25_rank DESC
    LIMIT match_count;
END;
$$;


-- ---------------------------------------------------------------------------
-- Grants
-- Allow the PostgREST roles (anon + authenticated) to execute both functions
-- so supabase.rpc() calls work without requiring superuser privileges.
-- ---------------------------------------------------------------------------

GRANT EXECUTE ON FUNCTION match_chunks_vector TO anon, authenticated;
GRANT EXECUTE ON FUNCTION match_chunks_bm25   TO anon, authenticated;
