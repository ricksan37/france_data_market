-- geographic_zone only takes three values. Singular test rather than
-- accepted_values: the generic test compiles a multi-value IN(), which the
-- DuckDB optimizer bug crashes on in a queried view. Project convention
-- since then, for any check on a set of values.
--
-- 'unknown' is a value in its own right, not a gap: 101 offers out of 960
-- have neither a postal code nor an INSEE code. Counting them as mainland
-- France by default would inflate it by 10% of the corpus on an assumption.

select job_offer_id, geographic_zone
from {{ ref('fct_job_offer') }}
where geographic_zone != 'mainland'
  and geographic_zone != 'overseas'
  and geographic_zone != 'unknown'
