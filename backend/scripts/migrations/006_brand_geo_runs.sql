-- Migration 006: brand_geo_runs table
--
-- Stores one synthesis result per GEO Intelligence pipeline run.
-- Each row captures the strategic analysis over all keywords for that run.
-- Delta tracking: compare any two run_at values to see how the narrative
-- and territory map changed over time.
--
-- Idempotent: safe to run on a project where 006 was already applied.

create table if not exists brand_geo_runs (
    id                      uuid        primary key default gen_random_uuid(),
    company                 text        not null,
    run_at                  timestamptz not null default now(),

    -- Core metrics
    mention_rate            float,
    gap_keyword_count       int,
    dominant_framing        text,
    strongest_tier          text,
    top_counter_positioning text,

    -- Strategic analysis fields
    narrative               text,
    critical_gap            text,
    framing_gap             text,
    peer_group_assessment   text,

    -- Structured territory and peer data (stored as jsonb for flexibility)
    owned_territories       jsonb,
    contested_territories   jsonb,
    absent_territories      jsonb,
    primary_peer_group      jsonb,

    created_at              timestamptz not null default now()
);

-- Primary lookup: latest run for a company
create index if not exists brand_geo_runs_company_run_idx
    on brand_geo_runs (company, run_at desc);
