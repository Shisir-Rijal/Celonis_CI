-- Migration 010: visualbranding_snapshots table
--
-- Stores structured Visual Branding Agent node outputs per pipeline run.
-- Unlike research_snapshots, each row is a CROSS-COMPETITOR analysis (no
-- `company` column) — e.g. one row is "the color spectrum/diversity/warm-
-- cool split across all tracked competitors as of this run".
--
-- source_fingerprint lets the graph's change-detection router (see
-- backend/app/agents/visualbranding/graph.py) skip re-running a node when
-- its raw source data (research_snapshots, node='visuals') hasn't changed
-- since the last run.
--
-- Idempotent: safe to run on a project where 010 was already applied.

create table if not exists visualbranding_snapshots (
    id                  uuid        primary key default gen_random_uuid(),

    run_at              timestamptz not null,

    -- Which visualbranding node produced this row
    node                text        not null,   -- 'colors' | 'fonts' | 'logos'
                                                 -- | 'images' | 'videos' | 'trends'

    -- Hash of the raw scraped data this analysis was built from
    source_fingerprint  text        not null,

    -- Full structured output from the node, serialised from the Pydantic model
    data                jsonb       not null,

    created_at          timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

-- Primary lookup: latest snapshot per node (change-detection + API reads)
create index if not exists visualbranding_snapshots_node_run_idx
    on visualbranding_snapshots (node, run_at desc);
