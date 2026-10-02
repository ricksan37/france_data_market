-- Singular test: employer_category is one of the four categories
-- int_employers_classified can produce.
--
-- "is null or not in": NOT IN alone returns no row for a NULL (NULL not in
-- (...) is unknown, not true), so an unclassified offer would pass.
-- dbt contract: 0 rows = pass, >= 1 row = fail.

select
    job_offer_id,
    employer_category
from {{ ref('int_employers_classified') }}
where employer_category is null
    or employer_category not in (
        'DIRECT_EMPLOYER',
        'INTERMEDIARY',
        'ANONYMOUS',
        'INTERMEDIARY_RECLASSIFIED'
    )
