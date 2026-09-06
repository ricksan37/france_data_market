-- The four employer categories partition the offers: their sum must land
-- exactly on total_offer_count. A gap signals either a category that
-- appeared without being reported in weekly_snapshot.py, or a miscount.
--
-- coalesce on reclassified_intermediary_offer_count: the column is empty
-- (not zero) on CI weeks, and NULL + 918 is NULL -- the test would then pass
-- silently instead of failing, exactly the kind of false negative we're
-- trying to avoid.
--
-- Checked by hand on the three existing weeks before writing this test:
-- 314+197+407 = 918, 335+205+420 = 960, 348+185+425 = 958. All three hold.

select week_start_date
from {{ ref('fct_weekly_market') }}
where anonymous_offer_count
    + intermediary_offer_count
    + coalesce(reclassified_intermediary_offer_count, 0)
    + direct_employer_offer_count
  != total_offer_count
