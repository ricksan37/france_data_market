-- Every cluster of identical listings has exactly one canonical one.
--
-- SEVERITY: ERROR. This is the invariant every per-listing count relies on:
-- zero canonicals would drop an entire cluster from a
-- `where is_canonical_listing`, two would count it twice. In both cases the
-- total would be wrong with nothing to signal it.
--
-- The zero case isn't theoretical. row_number() returns 1 for no row if the
-- sort column is NULL across the whole partition and the engine orders
-- differently than expected: exactly the kind of drift a test catches and a
-- code review doesn't.

select
    listing_signature,
    count(*) as cluster_size,
    count(case when is_canonical_listing then 1 end) as canonical_count
from {{ ref('fct_job_offer') }}
group by listing_signature
having count(case when is_canonical_listing then 1 end) != 1
