-- Every weekly key is the Monday of its ISO week: weekly_snapshot.py and
-- offer_presence.py key on it, and series_breaks is joined on it. A date
-- that isn't a Monday would split one week into several rows or make a
-- series break silently match nothing.
--
-- dayofweek() in DuckDB: 0 = Sunday, 1 = Monday.
-- dbt contract: 0 rows = pass, >= 1 row = fail.

select 'fct_weekly_market' as source, week_start_date
from {{ ref('fct_weekly_market') }}
where dayofweek(week_start_date) != 1

union all

select 'fct_weekly_market_flow' as source, week_start_date
from {{ ref('fct_weekly_market_flow') }}
where dayofweek(week_start_date) != 1

union all

select 'series_breaks' as source, week_start_date
from {{ ref('series_breaks') }}
where dayofweek(week_start_date) != 1
