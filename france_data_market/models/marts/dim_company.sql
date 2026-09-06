{{ config(materialized='table') }}

-- dim_company: grain = 1 SIREN.
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
qualify row_number() over (partition by siren order by job_offer_id) = 1
