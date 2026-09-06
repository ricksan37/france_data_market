-- Weekly market flow: what appears, what disappears.
-- Grain: 1 row = 1 actually recorded week.
--
-- WHY THIS TABLE EXISTS ALONGSIDE fct_weekly_market. That one measures the
-- ACCUMULATED CORPUS, which never shrinks: an offer seen once stays in it
-- forever. Measured 2026-08-31: of the 552 July offers, 463 had disappeared
-- from France Travail, and fct_job_offer still counted them. The flow is
-- therefore measured on actual presence in each pull, never on the
-- cumulative total.
--
-- READ THE RATES WITH weeks_since_previous. The first two recorded weeks
-- are six weeks apart, not one: an exit rate of 83.9% there covers a
-- six-week period. Exposing the gap rather than normalizing it away by
-- default leaves the choice to the analysis, and makes it impossible to
-- misread this figure as a weekly pace by mistake.
--
-- REAPPEARANCES. new_offer_count counts offers never seen before
-- (min(week_start_date) = t). An offer present in July, absent in August,
-- then reposted is therefore neither new nor a survivor: it enters the
-- active count without appearing in the reconciliation. The defect wasn't
-- observable over two weeks, where any offer absent from the first is
-- necessarily new; it surfaced at the third data point, in CI, and
-- assert_flow_conservation caught it. reappearance_count closes the
-- reconciliation without distorting new_offer_count, which keeps its market
-- meaning: a genuinely new offer.
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

-- Exits: present the previous recorded week, absent this one. Anti-join via
-- left join + is null rather than NOT IN: a NOT IN with several hundred
-- values crashes the DuckDB optimizer (known bug, version-independent).
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
    end as exit_rate_pct

from ordered as o
inner join active_offers as a on a.week_start_date = o.week_start_date
left join new_offers as n on n.week_start_date = o.week_start_date
left join exits as e on e.week_start_date = o.week_start_date
left join reappearances as r on r.week_start_date = o.week_start_date
