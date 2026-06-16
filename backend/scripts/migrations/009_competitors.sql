-- Migration 009: competitors table
--
-- Single source of truth for all tracked competitor domains.
-- Both the Research Agent scheduler and the Brand Intelligence Pipeline
-- read from this table to know which companies to analyse.
--
-- Idempotent: safe to run on a project where 009 was already applied.

-- ---------------------------------------------------------------------------
-- Table
-- ---------------------------------------------------------------------------

create table if not exists competitors (
    id         uuid        primary key default gen_random_uuid(),
    domain     text        not null unique,  -- e.g. 'celonis.com'
    name       text        not null,         -- display name, e.g. 'Celonis'
    active     boolean     not null default true,
    created_at timestamptz not null default now()
);

create index if not exists competitors_active_idx
    on competitors (active);

-- ---------------------------------------------------------------------------
-- Seed data
-- ---------------------------------------------------------------------------

insert into competitors (domain, name) values
    ('celonis.com',     'Celonis'),
    ('anthropic.com',   'Anthropic'),
    ('openai.com',      'OpenAI'),
    ('databricks.com',  'Databricks'),
    ('signavio.com',    'SAP Signavio'),
    ('palantir.com',    'Palantir'),
    ('servicenow.com',  'ServiceNow'),
    ('aris.com',        'ARIS'),
    ('ibm.com',         'IBM'),
    ('uipath.com',      'UiPath'),
    ('appian.com',      'Appian'),
    ('apromore.com',    'Apromore from Salesforce'),
    ('microsoft.com/en-us/microsoft-fabric', 'Microsoft Fabric')
on conflict (domain) do nothing;
