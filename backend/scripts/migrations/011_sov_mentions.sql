-- Migration 011: sov_mentions table
--
-- Stores classified mentions for the Share-of-Voice agent.
-- Each row is one news article or one SEO keyword sighting for one competitor,
-- enriched with theme / region / relevance classifications.
--
-- The agent reads raw research data from research_snapshots, builds Mention
-- objects, classifies them via LLM, and inserts the results here.
--
-- Dashboard reads are SQL aggregations directly on this table (no separate
-- aggregate table in MVP).
--
-- Idempotent: safe to run on a project where 011 was already applied.

-- ---------------------------------------------------------------------------
-- Table
-- ---------------------------------------------------------------------------

create table if not exists sov_mentions (
    id              uuid        primary key default gen_random_uuid(),
    run_at          timestamptz not null,                       -- when the agent ran
    company         text        not null,                       -- e.g. 'celonis.com'
    source_type     text        not null,                       -- 'news' | 'seo'
    source          text        not null,                       -- 'finnhub' | 'serper' | 'firecrawl' | 'google_serp'
    title           text        not null,
    content         text,
    date            date        not null,                       -- publication date (or research run date for SEO)
    month_bucket    text        not null,                       -- 'YYYY-MM', derived from date
    url             text        not null,
    language        text,
    themes          jsonb       not null default '[]'::jsonb,   -- list[str], e.g. ["Agentic AI"]
    region          text,                                        -- 'DACH' | 'Europe' | 'NA' | 'APAC' | 'Global'
    is_relevant     boolean     not null default true,
    reasoning       text,                                        -- one-sentence LLM rationale
    created_at      timestamptz not null default now(),

    -- Natural key: same article from same source for same company should
    -- only exist once, regardless of how many times the agent runs.
    constraint sov_mentions_natural_key unique (company, source_type, url)
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

create index if not exists sov_mentions_company_idx
    on sov_mentions (company);

create index if not exists sov_mentions_month_bucket_idx
    on sov_mentions (month_bucket);

create index if not exists sov_mentions_run_at_idx
    on sov_mentions (run_at desc);

-- GIN index allows fast filtering by themes, e.g. WHERE themes ? 'Agentic AI'
create index if not exists sov_mentions_themes_gin
    on sov_mentions using gin (themes);

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
-- Enable RLS without policies: this denies access via the public anon /
-- authenticated keys by default. The backend uses SUPABASE_SERVICE_ROLE_KEY
-- which bypasses RLS, so reads / writes from the SoV agent continue to work.
-- Matches the convention used for all other tables in this project.

alter table sov_mentions enable row level security;

