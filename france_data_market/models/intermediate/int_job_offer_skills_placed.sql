-- Every LLM-extracted skill mention of the offers in fct_job_offer, placed
-- in the list (technology or domain) the corpus agrees on.
-- Grain: one row per mention (an offer can mention a term more than once;
-- the fact tables deduplicate).
--
-- WHY. The extraction prompt separates products (installable, one vendor)
-- from concepts, but the LLM doesn't always follow it: on the 2026-09-26
-- dump, SQL sat in domains for 40 offers and CI/CD in technologies for 36,
-- so each list undercounted the other's terms. A term's placement across
-- the whole corpus is a better judge than any single extraction.
--
-- RULE. A term (case-insensitive) moves all its mentions to one list when
-- it has at least 10 mentions and that list holds at least twice as many as
-- the other. Below that, the majority is noise: with 3 mentions against 2,
-- concepts like "ingestion" or "conteneurisation" would have become
-- technologies. Mentions of such terms stay where the LLM put them. On the
-- 2026-09-26 dump the rule moves 292 mentions of 64 terms, every one of
-- them checked by hand (SQL, Python, Jira to technology; CI/CD, ETL, LLM to
-- domain).

with mentions as (

    select
        job_offer_id,
        unnest(technologies) as raw_term,
        'technology' as extracted_list
    from {{ ref('stg_extraction__skills') }}
    where extraction_status = 'ok'
        and job_offer_id in (select job_offer_id from {{ ref('fct_job_offer') }})

    union all

    select
        job_offer_id,
        unnest(domains) as raw_term,
        'domain' as extracted_list
    from {{ ref('stg_extraction__skills') }}
    where extraction_status = 'ok'
        and job_offer_id in (select job_offer_id from {{ ref('fct_job_offer') }})

),

keyed as (

    select
        job_offer_id,
        raw_term,
        lower(trim(raw_term)) as term_key,
        extracted_list
    from mentions

),

placement as (

    select
        term_key,
        count(*) filter (where extracted_list = 'technology') as technology_mentions,
        count(*) filter (where extracted_list = 'domain') as domain_mentions
    from keyed
    group by term_key

)

select
    k.job_offer_id,
    k.raw_term,
    k.term_key,
    k.extracted_list,
    case
        when p.technology_mentions + p.domain_mentions >= 10
            and p.technology_mentions >= 2 * p.domain_mentions
            then 'technology'
        when p.technology_mentions + p.domain_mentions >= 10
            and p.domain_mentions >= 2 * p.technology_mentions
            then 'domain'
        else k.extracted_list
    end as skill_list
from keyed as k
left join placement as p
    on k.term_key = p.term_key
