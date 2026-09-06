-- Grouping of job offers that are actually the same listing.
-- Grain: one row per job offer. Key: job_offer_id.
--
-- THE PROBLEM. stg_raw__ft_job_offers' deduplication works on job_offer_id:
-- it discards the API's index duplicates, not campaigns. Yet the same
-- position published in several cities gets one identifier per city, and so
-- counts that many times in every aggregate. Measured 2026-09-04: 152 offers
-- out of 960 share their text with at least one other, i.e. 15.8% of the
-- corpus. The largest cluster is one employer publishing the same listing in
-- 24 communes.
--
-- MEASURED CONSEQUENCES. SQL goes from 282 to 235 offers (-16.7%), Python
-- from 283 to 262, and Python moves clearly ahead of SQL when the two
-- seemed neck and neck. The salary median goes from 45,000 to 43,000 €.
-- These are not cosmetic adjustments.
--
-- NORMALIZED SIGNATURE, NOT A SIMILARITY THRESHOLD. Lowercase and collapsed
-- whitespace: seven more clusters than on raw text, and above all no
-- threshold to justify. Two texts are identical or they aren't. A similarity
-- measure would catch more -- across the eleven listings of an overseas
-- campaign, nine share exactly the same text and two have a slightly
-- different one -- but at the cost of an arbitrary threshold, which this
-- project doesn't introduce without a measurement to defend it.
-- False-cluster risk ruled out by measurement: the shortest description in
-- the corpus is 296 characters, only 17 fall under 500.
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
