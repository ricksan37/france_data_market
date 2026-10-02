-- Singular test: at least 75% of the offers in the latest DINUM dump must be
-- matched to a company (a match_* status). An empty dump fails too.
-- Measured: 80.3% on 213 offers (2026-08-01 run), 86.8% on 707 offers
-- (2026-09-26 run). The floor sits 5 points under the lower one: a drop
-- below it points to a regression of the matching rules or a change in the
-- API's answers, not to the market. Only two runs back this threshold, and a
-- small run (a few dozen offers) could fall under it by chance: revisit it
-- with a new measurement rather than lowering it to get a green build.
--
-- SEVERITY: ERROR, because stg_dinum__companies adopts the latest dump
-- automatically.
-- dbt contract: 0 rows = pass, 1 row = fail.
select
    count(*) as offer_count,
    count(*) filter (where match_status like 'match%') as matched_count,
    round(100.0 * count(*) filter (where match_status like 'match%') / nullif(count(*), 0), 1)
        as matching_rate_pct
from {{ ref('stg_dinum__companies') }}
having count(*) = 0
    or count(*) filter (where match_status like 'match%') < 0.75 * count(*)
