-- Flow conservation: a week's actives must be exactly the previous week's
-- actives, minus exits, plus new offers, plus reappearances.
--
--   552 - 463 + 408 + 0 = 497   (the first two measured weeks)
--
-- This is the flow model's strongest test: it ties together four
-- independently computed measurements (an aggregation, a first occurrence,
-- two symmetric anti-joins). If one drifts, the equality breaks.
--
-- It's already proven useful. The reappearance_count term was missing from
-- the first version: an offer reposted after an absence was neither new
-- nor a survivor and entered the actives without appearing in the
-- reconciliation. The defect was invisible over two weeks and the test
-- caught it at the third data point, in CI.
--
-- coalesce on the three terms: without it, a single NULL makes the
-- comparison unknown and the test passes SILENTLY instead of failing. That
-- happened in the same session on a week with no new offer. The first week
-- stays excluded by the clause on previous_active_offer_count: with no
-- predecessor, the equality is meaningless.

with flux as (

    select
        week_start_date,
        active_offer_count,
        new_offer_count,
        exit_count,
        reappearance_count,
        lag(active_offer_count) over (order by week_start_date) as previous_active_offer_count
    from {{ ref('fct_weekly_market_flow') }}

)

select week_start_date
from flux
where previous_active_offer_count is not null
  and active_offer_count != previous_active_offer_count
                    - coalesce(exit_count, 0)
                    + coalesce(new_offer_count, 0)
                    + coalesce(reappearance_count, 0)
