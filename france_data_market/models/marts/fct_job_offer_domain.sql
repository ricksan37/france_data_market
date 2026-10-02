{{ config(materialized='table') }}

-- Fine-grained fact table: 1 row = 1 (job offer, domain) pair.
-- A model distinct from fct_job_offer_technology rather than a single table
-- with a skill_type column: an explicit decision. Cost assumed: a question
-- spanning both kinds of terms will need a union all.
--
-- KNOWN LIMIT: the extraction model (mistral-nemo) under-extracts this
-- field on consulting listings. Domain counts are therefore floors, not
-- exact measurements. See extract_skills.py.
--
-- NORMALIZATION: 2310 distinct domain values for 5828 mentions on the
-- 2026-09-26 dump: lexical fragmentation (case, language, acronyms:
-- "BI"/"Business Intelligence", "Data Governance"/"gouvernance des
-- données") that makes the raw field unusable for a group by. A mapping
-- (seeds/mapping_domaines.csv) normalizes the 12 most frequent clusters
-- (>60 cumulative occurrences each) to a canonical form. The long tail
-- (values with 1-10 occurrences) is NOT mapped: no rule built on a sample
-- too thin to defend (project principle, cf. assert_annual_salary_bounds).
-- raw_domain stays the audit source; normalized_domain equals raw_domain
-- unchanged when no match exists in the mapping.
-- Restricted to offers in fct_job_offer: the extraction dumps cover every
-- offer ever extracted, fct_job_offer only the latest pull.
--
-- COUNTING. The grain is (offer, raw_domain), deduplicated with distinct
-- because the LLM sometimes lists a value twice. Two variants of the same
-- domain in one offer ("Gouvernance des données" and "Data Governance")
-- stay two rows with the same normalized_domain (4 offers on the 2026-09-26
-- dump): count offers per domain with count(distinct job_offer_id).
select distinct
    d.job_offer_id,
    d.domain as raw_domain,
    coalesce(m.canonical_domain, d.domain) as normalized_domain
from (
    select
        job_offer_id,
        unnest(domains) as domain
    from {{ ref('stg_extraction__skills') }}
    where extraction_status = 'ok'
        and job_offer_id in (select job_offer_id from {{ ref('fct_job_offer') }})
) as d
left join {{ ref('mapping_domaines') }} as m
    on d.domain = m.variant
