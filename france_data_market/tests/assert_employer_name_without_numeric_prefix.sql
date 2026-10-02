{{ config(
    severity = 'warn',
    tags = ['known_issue']
) }}

-- Detects employer names on the current offers carrying a parasitic numeric
-- prefix: an internal recruiter identifier (service code, HR reference)
-- glued in front of the real name, separated by a hyphen. Measured
-- examples: "751163-DIR STRATEGIE INNOVATION ET TRANSFO", "929840-PARIS
-- DIRECTION DES SI COLISSIMO". Not a usable employer name as-is: DINUM
-- leaves both unresolved.
--
-- SEVERITY: WARN, a watch rather than a cleanup. Two occurrences are too
-- few to prove that "digits + hyphen" is a stable pattern without false
-- positives (a name like "3M" or "42Data"). If the count grows, it becomes
-- the signal to build a real cleanup (regexp_replace in staging).
--
-- dbt contract: 0 rows = pass, >= 1 row = warn (not fail).

select
    job_offer_id,
    employer_name_raw
from {{ ref('stg_raw__ft_job_offers') }}
where regexp_matches(employer_name_raw, '^[0-9]+-')
