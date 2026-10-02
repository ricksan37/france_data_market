{{ config(
    severity = 'warn',
    tags = ['known_issue']
) }}

-- Singular test: no annual offer should have a salary_min outside the
-- plausibility range [10000, 300000].
-- Limited to salary_period = 'annual': the hourly/monthly bounds aren't
-- measured, decision deferred.
--
-- SEVERITY: WARN, a COUNTER. Outlier amounts are recruiter entry errors
-- (a monthly salary or an hourly rate typed in the annual field; 1 offer at
-- 9500 EUR on the 2026-09-26 dump). They are flagged, not fixed: the rule
-- lives in annual_salary_plausible (int_job_offer_salary_parsed), protected
-- by assert_plausible_salary_flag at severity error, and aggregations
-- filter on that flag. Failing here would block the pipeline on a known,
-- accepted state; the warning keeps the count visible, and a spike means
-- the source has changed.
--
-- dbt contract: 0 rows = pass, >= 1 row = warn (not fail).

select
    job_offer_id,
    salary_min,
    salary_period
from {{ ref('fct_job_offer') }}
where salary_period = 'annual'
  and (salary_min < 10000 or salary_min > 300000)
