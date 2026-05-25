-- Migration 001: chunks table
--
-- Creates the single corpus table for the RAG store. All ingested content
-- lands here as chunks, regardless of source. Supports both vector similarity
-- search (pgvector / ivfflat) and BM25 keyword search (tsvector / GIN).
--
-- Prerequisites:
--   - pgvector extension enabled (Supabase: Database → Extensions → vector)
--
-- Idempotent: safe to run on a project where 001 was already applied.

-- Enable pgvector if not already enabled.
create extension if not exists vector;

-- ---------------------------------------------------------------------------
-- Main table
-- ---------------------------------------------------------------------------

create table if not exists chunks (
    id          uuid        primary key default gen_random_uuid(),
    content     text        not null,
    -- JSON mirror of ChunkMetadata (company, source_type, source_origin,
    -- date, url, title, language, topic, content_type, visual_type,
    -- chunking_strategy).  Stored as jsonb so Postgres can index individual
    -- fields for metadata pre-filtering.
    metadata    jsonb       not null default '{}',
    -- OpenAI text-embedding-3-small produces 1 536-dimensional vectors.
    embedding   vector(1536),
    -- Generated column: updated automatically whenever content changes.
    -- Used for BM25 / full-text search via plainto_tsquery.
    content_tsv tsvector    generated always as
                                (to_tsvector('english', content)) stored,
    created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

-- ivfflat index for approximate nearest-neighbour vector search.
-- lists=100 is a reasonable default for up to ~1 M rows; tune upward
-- (lists ≈ sqrt(rows)) if the corpus grows significantly.
-- cosine distance matches the similarity metric used in retrieval.
create index if not exists chunks_embedding_ivfflat_idx
    on chunks
    using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);

-- GIN index for fast tsvector full-text search (BM25 via ts_rank_cd).
create index if not exists chunks_content_tsv_gin_idx
    on chunks
    using gin (content_tsv);

-- GIN index on metadata for jsonb containment / key-path pre-filtering
-- (e.g. WHERE metadata @> '{"source_origin": "owned"}').
create index if not exists chunks_metadata_gin_idx
    on chunks
    using gin (metadata);
