{{ config(
    severity = 'warn',
    tags = ['known_issue']
) }}

-- Singular test: no annual offer should have a salary_min outside the
-- plausibility range [10000, 300000].
-- Limited to salary_period = 'annual': the hourly/monthly bounds aren't
-- measured, decision deferred.
--
-- SEVERITY: WARN, and this test deliberately stays a COUNTER. It measures
-- how many outlier values exist; it was never meant to exclude them from
-- an aggregation.
--
-- The condition set previously is met. It said: "if a 2nd case shows up
-- one day with new data, that changes things." As of 2026-09-03, out of
-- 960 offers, there are 15, spread across four distinct sources and two
-- consistent mechanisms: a monthly salary labeled annual (11 listings from
-- the same advertiser, all at 1800 €) and an hourly rate labeled annual (4
-- listings, 15 to 40 €). The rule was therefore written, but elsewhere:
-- annual_salary_plausible in int_job_offer_salary, protected by
-- assert_plausible_salary_flag at severity error.
--
-- Why this test doesn't move to error regardless: the 15 rows exist and
-- will keep existing, since we chose to flag them rather than fix them.
-- Failing it would block the pipeline on a known, accepted state. Its WARN
-- keeps the count visible on every run, which stays useful: if the number
-- spikes, the source has changed.
--
-- dbt contract: 0 rows = pass, >= 1 row = warn (not fail).

select
    job_offer_id,
    salary_min,
    salary_period
from {{ ref('fct_job_offer') }}
where salary_period = 'annual'
  and (salary_min < 10000 or salary_min > 300000)
