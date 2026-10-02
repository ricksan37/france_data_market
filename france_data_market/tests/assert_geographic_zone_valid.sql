-- Singular test: geographic_zone takes only three values. 'unknown' is a
-- value in its own right, for offers with neither a postal code nor an
-- INSEE code (62 of 854 on the 2026-09-26 dump): counting them as mainland
-- France by default would rest on an assumption.
--
-- "is null or not in": NOT IN alone returns no row for a NULL (NULL not in
-- (...) is unknown, not true), so a missing zone would pass.
-- dbt contract: 0 rows = pass, >= 1 row = fail.

select
    job_offer_id,
    geographic_zone
from {{ ref('fct_job_offer') }}
where geographic_zone is null
    or geographic_zone not in ('mainland', 'overseas', 'unknown')
