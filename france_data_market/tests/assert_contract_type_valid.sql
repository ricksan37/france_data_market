-- Singular test: contract_type is one of the France Travail codes seen in
-- the scope: CDI, CDD, MIS (temporary agency), LIB (profession libérale),
-- CCE (profession commerciale). Tested on the staging model, the column's
-- source: fct_job_offer copies it unchanged.
--
-- "is null or not in": NOT IN alone returns no row for a NULL (NULL not in
-- (...) is unknown, not true), so a missing contract type would pass.
-- dbt contract: 0 rows = pass, >= 1 row = fail.

select
    job_offer_id,
    contract_type
from {{ ref('stg_raw__ft_job_offers') }}
where contract_type is null
    or contract_type not in ('CDI', 'CDD', 'MIS', 'LIB', 'CCE')
