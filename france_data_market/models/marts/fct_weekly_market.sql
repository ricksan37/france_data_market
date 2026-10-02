{{ config(materialized='table') }}

-- Weekly fact: state of the market, week by week.
-- Grain: 1 row = 1 ISO week (Monday). One row per week is guaranteed at the
-- source by weekly_snapshot.py's upsert and checked here by a unique test.
--
-- WHAT total_offer_count MEASURES. weekly_snapshot.py counts fct_job_offer
-- right after the weekly pull, and fct_job_offer holds the latest dump only:
-- each point is the market as returned by that week's pull. Points measured
-- under an earlier method or scope stay in the series; is_series_break
-- flags the first week of each new method (seeds/series_breaks.csv), where
-- the change from the previous week reflects the pipeline, not the market.
--
-- offer_count_change is NULL on the first week: the absence of a comparison
-- point isn't a zero change. Same principle as the empty
-- reclassified_intermediary_offer_count cell in CI.

with weekly as (

    select * from {{ ref('stg_history__weekly_market') }}

),

series_breaks as (

    select * from {{ ref('series_breaks') }}

)

select
    w.week_start_date,
    w.total_offer_count,
    w.anonymous_offer_count,
    w.intermediary_offer_count,
    w.reclassified_intermediary_offer_count,
    w.direct_employer_offer_count,
    w.median_annual_salary,
    w.top_technology,
    w.llm_extraction_available,

    w.total_offer_count - lag(w.total_offer_count) over (order by w.week_start_date)
        as offer_count_change,

    -- nullif: a week with zero offers would be an anomaly to diagnose, not
    -- a reason to fail the mart's build.
    round(w.anonymous_offer_count * 100.0 / nullif(w.total_offer_count, 0), 1)
        as anonymous_rate_pct,

    round(w.direct_employer_offer_count * 100.0 / nullif(w.total_offer_count, 0), 1)
        as direct_employer_rate_pct,

    b.week_start_date is not null as is_series_break

from weekly as w
left join series_breaks as b
    on w.week_start_date = b.week_start_date
