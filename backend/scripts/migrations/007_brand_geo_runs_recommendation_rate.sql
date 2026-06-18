-- Migration 007: add recommendation_rate to brand_geo_runs
--
-- recommendation_rate = count of sightings where recommendation_strength
-- in ('recommended', 'default') / total keywords in the run.
-- Needed for geo_score computation in the API endpoint:
--   geo_score = mention_rate * 0.4 + recommendation_rate * 0.6
--
-- Idempotent: safe to run if column already exists.

alter table brand_geo_runs
    add column if not exists recommendation_rate float;
