-- Migration 011: rename recommendation_strength value 'default' → 'organic'
--
-- 'default' was misleading (sounds like a fallback/code default).
-- 'organic' better reflects the concept: the brand is mentioned unprompted
-- as the first / go-to choice — top-of-mind, strongest GEO signal.

update brand_geo_sightings
set recommendation_strength = 'organic'
where recommendation_strength = 'default';
