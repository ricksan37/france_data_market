{{ config(
    severity = 'warn',
    tags = ['known_issue']
) }}

-- Detects employer names (from the raw offer, before DINUM matching)
-- carrying a parasitic numeric prefix: an internal recruiter identifier
-- (service code, HR reference) glued in front of the real name, separated
-- by a hyphen. Measured examples: "751163-DIR STRATEGIE INNOVATION ET
-- TRANSFO", "929840-PARIS DIRECTION...". Not a usable employer name as-is.
--
-- SEVERITY: WARN, decision accepted on 2026-08-01: 2 occurrences out of
-- 213, not enough to build a defensible cleanup rule (project principle:
-- never correct on an isolated case, and 2 cases don't yet guarantee that
-- the "digits + hyphen" pattern is stable, without a false positive like
-- "3M" or "42Data"). The WARN keeps the pipeline green while watching for
-- drift: if this number grows with new data, it becomes a signal to build
-- real cleanup (regexp_replace in staging) rather than a simple alert.
--
-- dbt contract: 0 rows = pass, >= 1 row = warn (not fail).

select
    job_offer_id,
    employer_name_raw
from {{ ref('stg_dinum__companies') }}
where regexp_matches(employer_name_raw, '^[0-9]+-')
