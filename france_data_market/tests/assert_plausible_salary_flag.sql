-- Consistency of the annual_salary_plausible flag with the bounds it summarizes.
--
-- SEVERITY: ERROR. Annual salary aggregations exclude implausible amounts
-- by filtering on this flag, so the flag is the rule and this test protects
-- it. assert_annual_salary_bounds only counts the outliers (warn).
--
-- Three ways to break it, all caught here:
--   1. flag true on a value outside the bounds
--   2. flag false on a value within the bounds
--   3. flag absent when the question applies (annual period and amount
--      given) -- the most insidious case, because a NULL silently
--      disappears from any `where annual_salary_plausible` filter, and an
--      unhandled NULL doesn't fail a test, it passes it.
-- dbt contract: 0 rows = pass, >= 1 row = fail.

select
    job_offer_id,
    salary_period,
    salary_min,
    annual_salary_plausible
from {{ ref('fct_job_offer') }}
where
    -- 1 and 2: the flag doesn't say what the bounds say
    (
        annual_salary_plausible is not null
        and annual_salary_plausible != (salary_min >= 10000 and salary_min <= 300000)
    )
    -- 3: the question applies and the flag doesn't answer
    or (
        annual_salary_plausible is null
        and salary_period = 'annual'
        and salary_min is not null
    )
