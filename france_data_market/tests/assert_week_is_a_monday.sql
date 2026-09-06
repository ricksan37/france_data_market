-- The snapshot's key is the Monday of the ISO week (weekly_snapshot.py,
-- function lundi_de_la_semaine). A date that isn't a Monday signals a
-- regression to the old key (the run date), which had produced three
-- distinct rows for the single week of 2026-08-09.
--
-- dayofweek() in DuckDB: 0 = Sunday, 1 = Monday. Comparison to a single
-- value, so the known DuckDB optimizer bug doesn't apply here.

select week_start_date
from {{ ref('fct_weekly_market') }}
where dayofweek(week_start_date) != 1
