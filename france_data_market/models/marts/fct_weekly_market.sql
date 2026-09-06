-- Weekly fact: state of the offer corpus, week by week.
-- Grain: 1 row = 1 ISO week (Monday). Uniqueness is guaranteed at the
-- source by weekly_snapshot.py's upsert, and verified here by a test rather
-- than assumed -- the old append-only write had produced three rows for the
-- single week of 2026-08-09.
--
-- SCOPE OF THE MEASUREMENT, to read before interpreting a chart:
-- total_offer_count counts the ACCUMULATED CORPUS (deduplicated union of
-- every dump present on disk), not the offers active on France Travail that
-- week. A July offer removed from the API stays counted there. Measuring
-- the actual flow -- appearances, disappearances -- needs a history at the
-- offer's grain, beyond the reach of an aggregate file. Documented here so
-- no one reads this table as a market measurement.
--
-- offer_count_change is NULL on the first week: the absence of a comparison
-- point isn't a zero change. Same principle as the empty
-- reclassified_intermediary_offer_count cell in CI.

with hebdo as (

    select * from {{ ref('stg_history__weekly_market') }}

)

select
    week_start_date,
    total_offer_count,
    anonymous_offer_count,
    intermediary_offer_count,
    reclassified_intermediary_offer_count,
    direct_employer_offer_count,
    median_annual_salary,
    top_technology,
    llm_extraction_available,

    total_offer_count - lag(total_offer_count) over (order by week_start_date)
        as offer_count_change,

    -- nullif: a week with zero offers would be an anomaly to diagnose, not
    -- a reason to fail the mart's build.
    round(anonymous_offer_count * 100.0 / nullif(total_offer_count, 0), 1)
        as anonymous_rate_pct,

    round(direct_employer_offer_count * 100.0 / nullif(total_offer_count, 0), 1)
        as direct_employer_rate_pct

from hebdo
