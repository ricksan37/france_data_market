-- Singular test: employer_category must never take a value outside the 4
-- known categories. As with contract_type, we avoid accepted_values / IN /
-- NOT IN, which trigger the DuckDB 1.5.4 optimizer bug (INTERNAL Error:
-- index 4 within vector of size 4).
-- dbt contract: 0 rows = pass, >= 1 row = fail.
select
    job_offer_id,
    employer_category
from {{ ref('int_employer_classification') }}
where employer_category != 'DIRECT_EMPLOYER'
  and employer_category != 'INTERMEDIARY'
  and employer_category != 'ANONYMOUS'
  and employer_category != 'INTERMEDIARY_RECLASSIFIED'
