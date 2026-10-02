{{ config(materialized='table') }}

-- Fine-grained fact table: 1 row = 1 (job offer, technology) pair.
-- This grain is what lets you count how many offers ask for Python: a
-- simple group by technology, impossible on a LIST column.
--
-- Offers with no technology at all (213 of 854 on the 2026-09-26 dump,
-- mostly consulting listings) DISAPPEAR here: unnest on an empty list
-- produces no row. This isn't data loss: fct_job_offer remains the
-- reference table for counting offers. This model is for counting term
-- occurrences, not offers.
--
-- Restricted to offers in fct_job_offer: the extraction dumps cover every
-- offer ever extracted, fct_job_offer only the latest pull.
--
-- CASE. The LLM writes the same technology in several casings ("Power BI" /
-- "Power Bi", "dbt" / "DBT" / "Dbt"): 43 technologies on the 2026-09-26
-- dump, none of them merging two distinct technologies. Mentions are
-- grouped case-insensitively and shown under the corpus's most frequent
-- spelling (alphabetical on a tie). Spacing variants ("PowerBI",
-- "Datalake") are not merged: no rule checked yet. The raw spelling stays
-- in stg_extraction__skills.

with mentions as (

    select
        job_offer_id,
        unnest(technologies) as raw_technology
    from {{ ref('stg_extraction__skills') }}
    where extraction_status = 'ok'
        and job_offer_id in (select job_offer_id from {{ ref('fct_job_offer') }})

),

keyed as (

    select
        job_offer_id,
        raw_technology,
        lower(trim(raw_technology)) as technology_key
    from mentions

),

spellings as (

    select
        technology_key,
        raw_technology as technology
    from keyed
    group by technology_key, raw_technology
    qualify row_number() over (
        partition by technology_key
        order by count(*) desc, raw_technology
    ) = 1

)

-- distinct on the pair: the LLM sometimes lists the same technology twice
-- in one offer, which would break the grain.
select distinct
    k.job_offer_id,
    s.technology
from keyed as k
left join spellings as s
    on k.technology_key = s.technology_key
