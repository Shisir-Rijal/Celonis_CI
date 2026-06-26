-- Migration 008: research_snapshots table
--
-- Stores structured Research Agent node outputs per company per run.
-- One row per node per pipeline run — enables delta tracking across cadences.
--
-- Idempotent: safe to run on a project where 008 was already applied.

-- ---------------------------------------------------------------------------
-- Main table
-- ---------------------------------------------------------------------------

create table if not exists research_snapshots (
    id          uuid        primary key default gen_random_uuid(),

    -- Which company was scraped and when
    company     text        not null,   -- competitor domain, e.g. 'celonis.com'
    run_at      timestamptz not null,

    -- Which research node produced this row
    node        text        not null,   -- 'financials' | 'news' | 'events' | 'seogeo'
                                        -- | 'newsletter' | 'positioning' | 'socials'
                                        -- | 'youtube' | 'visuals' | 'wording'

    -- Full structured output from the node, serialised from the Pydantic model
    data        jsonb       not null,

    created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

-- Primary lookup: all snapshots for a company ordered by recency
create index if not exists research_snapshots_company_run_idx
    on research_snapshots (company, run_at desc);

-- Filter by node across runs (for delta/trend queries per data type)
create index if not exists research_snapshots_company_node_idx
    on research_snapshots (company, node);
