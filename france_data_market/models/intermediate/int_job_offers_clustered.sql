-- Grouping of job offers that are actually the same listing.
-- Grain: one row per job offer. Key: job_offer_id.
--
-- THE PROBLEM. stg_raw__ft_job_offers deduplicates on job_offer_id, but a
-- recruiter who publishes the same listing several times, in several
-- communes or again in the same one, gets one identifier per publication:
-- every copy counts in every aggregate. 2026-09-26 dump: 53 offers out of
-- 854 (6.2%) share their text with at least one other, in 21 clusters. The
-- largest is one employer publishing the same listing in 12 communes; 13
-- clusters stay within a single commune (reposts).
--
-- MEASURED CONSEQUENCES (same dump). Counting listings instead of offers
-- takes SQL from 256 to 238 offers (-7%) and Python from 261 to 255. The
-- median annual salary stays at 45000 EUR.
--
-- NORMALIZED SIGNATURE, NOT A SIMILARITY THRESHOLD. Lowercase and collapsed
-- whitespace, then md5: two texts are identical or they aren't, so there is
-- no threshold to justify. Normalization finds 21 clusters where the raw
-- text finds 20. A similarity measure would also catch near-identical
-- texts, at the cost of an arbitrary threshold this project doesn't
-- introduce without a measurement to defend it.
-- False-cluster risk checked on the same dump: no cluster mixes two named
-- employers; the shortest description is 191 characters, 10 are under 500.
--
-- WE FLAG, WE DON'T DROP. No offer is discarded: every analysis chooses to
-- count offers or listings. Both questions are legitimate and don't share
-- the same answer.

with signatures as (

    select
        job_offer_id,
        job_offer_creation_date,
        md5(lower(regexp_replace(trim(job_description), '\s+', ' ', 'g')))
            as listing_signature
    from {{ ref('stg_raw__ft_job_offers') }}

)

select
    job_offer_id,
    listing_signature,
    count(*) over (partition by listing_signature) as cluster_size,

    -- The canonical one is the OLDEST of the cluster: it's the original
    -- publication, the following ones are reposts. job_offer_id breaks ties
    -- on equal dates, so the result doesn't depend on read order.
    row_number() over (
        partition by listing_signature
        order by job_offer_creation_date, job_offer_id
    ) = 1 as is_canonical_listing

from signatures
