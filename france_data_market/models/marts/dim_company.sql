{{ config(materialized='table') }}

-- dim_company: grain = 1 SIREN.
-- Restricted to the companies of current DIRECT_EMPLOYER offers: the latest
-- DINUM dump also covers offers that have left the corpus or been
-- reclassified as intermediaries since it was run (2026-09-26 dump: 317
-- SIRENs, 155 of them current). Filtered on int_employers_classified rather
-- than fct_job_offer, so the dimension doesn't depend on the fact table
-- that references it.
-- age_years is a raw measurement (company_creation_date -> today), not a
-- judgment call. Deliberately no is_startup flag: the trio of age + NAF +
-- headcount doesn't reliably distinguish a startup from any other SME, and
-- a threshold frozen here would be a decision hidden in the mart rather
-- than a visible one at analysis time. The three signals (age_years,
-- company_naf_code, employee_count_range) stay separate so the threshold
-- gets set at analysis time, not here.

select
    siren,
    siret_headquarters,
    company_legal_name,
    company_naf_code,
    company_naf_section,
    employee_count_range,
    employee_count_reference_year,
    company_category,
    company_creation_date,
    date_diff('year', company_creation_date, current_date) as age_years,
    establishment_count,
    headquarters_city,
    headquarters_postal_code
from {{ ref('stg_dinum__companies') }}
where siren is not null
    and job_offer_id in (
        select job_offer_id
        from {{ ref('int_employers_classified') }}
        where employer_category = 'DIRECT_EMPLOYER'
    )
qualify row_number() over (partition by siren order by job_offer_id) = 1
