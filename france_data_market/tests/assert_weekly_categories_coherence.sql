-- The four employer categories partition the offers: their sum must land
-- exactly on total_offer_count. A gap signals either a category that
-- appeared without being reported in weekly_snapshot.py, or a miscount.
--
-- coalesce on reclassified_intermediary_offer_count: the column is empty
-- (not zero) on CI weeks, and NULL + 918 is NULL -- the test would then pass
-- silently instead of failing.
--
-- Example (week of 2026-08-10, a CI week): 314 + 197 + 0 + 407 = 918.
-- dbt contract: 0 rows = pass, >= 1 row = fail.

select week_start_date
from {{ ref('fct_weekly_market') }}
where anonymous_offer_count
    + intermediary_offer_count
    + coalesce(reclassified_intermediary_offer_count, 0)
    + direct_employer_offer_count
  != total_offer_count
