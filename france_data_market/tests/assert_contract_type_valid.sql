-- Singular test: no offer should have a contract_type outside the known list.
-- NB: we use NEITHER accepted_values NOR NOT IN. Both trigger an internal
-- DuckDB 1.5.4 optimizer bug (INTERNAL Error: index 4 within vector of
-- size 4, in RemoveUnusedColumns/SumRewriterOptimizer). Chained != take a
-- different compilation path and avoid it.
-- dbt contract: 0 rows = pass, >= 1 row = fail.

select
    job_offer_id,
    contract_type
from {{ ref('stg_raw__ft_job_offers') }}
where contract_type != 'CDI'
  and contract_type != 'CDD'
  and contract_type != 'MIS'
  and contract_type != 'LIB'
  and contract_type != 'CCE'
