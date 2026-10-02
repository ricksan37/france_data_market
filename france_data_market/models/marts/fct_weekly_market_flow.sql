{{ config(materialized='table') }}

-- Weekly market flow: what appears, what disappears.
-- Grain: 1 row = 1 actually recorded week.
--
-- WHY THIS TABLE EXISTS ALONGSIDE fct_weekly_market. That one counts each
-- week's pull; it can't say which offers appeared or left. The flow is
-- measured at the offer's grain, on the presence of each offer in each pull
-- (offer_presence.csv, built from the raw dumps).
--
-- READ THE RATES WITH weeks_since_previous. Recorded weeks are not always
-- consecutive (the first two are six weeks apart): an exit rate then covers
-- the whole gap. Exposing the gap rather than normalizing it away leaves
-- the choice to the analysis and prevents reading it as a weekly pace.
--
-- READ THE CHANGES WITH is_series_break. On the first week of a new method
-- or scope (seeds/series_breaks.csv), exits and new offers measure the
-- change of pipeline, not the market.
--
-- REAPPEARANCES. new_offer_count counts offers never seen before
-- (min(week_start_date) = t). An offer present, then absent, then reposted
-- is neither new nor a survivor: without reappearance_count it would enter
-- the active count without appearing in the reconciliation that
-- assert_flow_conservation checks. A separate term keeps new_offer_count's
-- market meaning: a genuinely new offer.
--
-- exit_count, reappearance_count and exit_rate_pct are NULL on the first
-- week: no earlier week to compare against. An absence of comparison isn't
-- a zero exit -- same principle as offer_count_change in fct_weekly_market.
-- new_offer_count, on the other hand, is 0 and not NULL when no new offer
-- appears: the measurement was actually made.

with presence as (

    select
        week_start_date,
        job_offer_id
    from {{ ref('stg_presence__job_offer_presence') }}

),

-- The ACTUALLY recorded weeks, not a continuous calendar: a missed run
-- leaves a gap, which weeks_since_previous makes visible.
weeks as (

    select distinct week_start_date from presence

),

ordered as (

    select
        week_start_date,
        lag(week_start_date) over (order by week_start_date) as previous_week_start_date
    from weeks

),

first_seen as (

    select
        job_offer_id,
        min(week_start_date) as first_seen_week
    from presence
    group by job_offer_id

),

active_offers as (

    select week_start_date, count(*) as active_offer_count
    from presence
    group by week_start_date

),

new_offers as (

    select first_seen_week as week_start_date, count(*) as new_offer_count
    from first_seen
    group by 1

),

-- Exits: present the previous recorded week, absent this one. An explicit
-- anti-join (left join + is null): it reads as "no matching row", and it
-- avoids NOT IN's trap, where a single NULL in the subquery makes every
-- comparison unknown and returns no row.
exits as (

    select
        o.week_start_date,
        count(*) as exit_count
    from ordered as o
    inner join presence as previous_presence
        on previous_presence.week_start_date = o.previous_week_start_date
    left join presence as current_presence
        on current_presence.job_offer_id = previous_presence.job_offer_id
        and current_presence.week_start_date = o.week_start_date
    where current_presence.job_offer_id is null
    group by o.week_start_date

),

-- Reappearances: present this week, absent the previous one, but already
-- seen earlier. The exact symmetric of exits.
reappearances as (

    select
        o.week_start_date,
        count(*) as reappearance_count
    from ordered as o
    inner join presence as current_presence
        on current_presence.week_start_date = o.week_start_date
    inner join first_seen as fs
        on fs.job_offer_id = current_presence.job_offer_id
    left join presence as previous_presence
        on previous_presence.job_offer_id = current_presence.job_offer_id
        and previous_presence.week_start_date = o.previous_week_start_date
    where previous_presence.job_offer_id is null
      and fs.first_seen_week < o.week_start_date
    group by o.week_start_date

),

series_breaks as (

    select * from {{ ref('series_breaks') }}

)

select
    o.week_start_date,
    date_diff('week', o.previous_week_start_date, o.week_start_date)
        as weeks_since_previous,
    a.active_offer_count,

    -- 0 and not NULL: a week with no new offer is a measurement, not an
    -- absence of measurement.
    coalesce(n.new_offer_count, 0) as new_offer_count,

    -- NULL on the first week only, 0 after that.
    case when o.previous_week_start_date is null then null
         else coalesce(e.exit_count, 0) end as exit_count,
    case when o.previous_week_start_date is null then null
         else coalesce(r.reappearance_count, 0) end as reappearance_count,

    round(100.0 * coalesce(n.new_offer_count, 0) / nullif(a.active_offer_count, 0), 1)
        as renewal_rate_pct,

    -- Measured against the PREVIOUS week's active count: an exit is
    -- measured against the population that could exit, not the one that
    -- remains.
    --
    -- Same coalesce as the exit_count column, and for the same reason: the
    -- CTE produces no row when nobody exits, and reading its raw value
    -- showed NULL where the rate is actually 0.0%. A week with no departure
    -- is a measurement, not an absence of measurement; only the first week
    -- stays NULL.
    case when o.previous_week_start_date is null then null
         else round(100.0 * coalesce(e.exit_count, 0)
                    / nullif(lag(a.active_offer_count) over (order by o.week_start_date), 0), 1)
    end as exit_rate_pct,

    b.week_start_date is not null as is_series_break

from ordered as o
inner join active_offers as a on a.week_start_date = o.week_start_date
left join new_offers as n on n.week_start_date = o.week_start_date
left join exits as e on e.week_start_date = o.week_start_date
left join reappearances as r on r.week_start_date = o.week_start_date
left join series_breaks as b on b.week_start_date = o.week_start_date
