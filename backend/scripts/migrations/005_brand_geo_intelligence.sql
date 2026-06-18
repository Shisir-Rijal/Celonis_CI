-- Migration 005: brand_geo_sightings table
--
-- Stores GEO Intelligence analysis results per keyword per run.
-- One row per keyword per LLM per pipeline run.
-- Delta tracking is automatic via run_at — compare two timestamps.
--
-- Idempotent: safe to run on a project where 005 was already applied.

-- ---------------------------------------------------------------------------
-- Main table
-- ---------------------------------------------------------------------------

create table if not exists brand_geo_sightings (
    id                      uuid        primary key default gen_random_uuid(),

    -- Which company was analysed and when
    company                 text        not null,
    run_at                  timestamptz not null default now(),

    -- Keyword metadata
    keyword                 text        not null,
    tier                    text        not null,   -- 'brand_category' | 'use_case' | 'competitor_trigger'

    -- Which LLM was queried
    llm                     text        not null,   -- e.g. 'gpt-4o-mini'

    -- Raw mention signal
    mentioned               boolean     not null default false,
    context                 text,                   -- excerpt from LLM response, null if not mentioned
    raw_response            text,                   -- full LLM answer for auditing

    -- Structured insight layers (null if not mentioned or analysis failed)
    co_mentioned_companies  jsonb,                  -- list of other companies named alongside
    framing                 text,                   -- 'technical' | 'strategic' | 'visionary'
    recommendation_strength text,                   -- 'listed' | 'attributed' | 'recommended' | 'default'
    use_case_context        text,                   -- e.g. 'supply chain transformation'
    counter_positioning     text,                   -- e.g. 'expensive for mid-market'

    created_at              timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

-- Primary lookup: all sightings for a company in a given run
create index if not exists brand_geo_sightings_company_run_idx
    on brand_geo_sightings (company, run_at desc);

-- Filter by keyword across runs (for delta/trend queries)
create index if not exists brand_geo_sightings_keyword_idx
    on brand_geo_sightings (company, keyword);

-- Filter by tier
create index if not exists brand_geo_sightings_tier_idx
    on brand_geo_sightings (company, tier);
