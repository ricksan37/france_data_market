-- Fine-grained fact table: 1 row = 1 (job offer, technology) pair.
-- This grain is what lets you count how many offers ask for Python: a
-- simple group by technology, impossible on a LIST column.
--
-- Offers with no technology at all (consulting listings, ~60% of the
-- tested sample) DISAPPEAR here: unnest on an empty list produces no row.
-- This isn't data loss: fct_job_offer remains the reference table for
-- counting offers. This model is for counting term occurrences, not offers.
select
    job_offer_id,
    unnest(technologies) as technology
from {{ ref('stg_extraction__skills') }}
where extraction_status = 'ok'
