-- Staging model for the DINUM company-enrichment dump.
-- No business logic here: flattening, renaming, casting only. Grain is
-- 1 row = 1 enriched job offer, not yet 1 row = 1 SIREN (a company can post
-- several offers).

with source as (

    select * from {{ source('dinum', 'companies') }}

),

unnested as (

    select t.r as r
    from source as s,
        unnest(s.resultats) as t(r)

),

renamed as (

    select
        r.job_offer_id as job_offer_id,
        r.employer_name_on_offer as employer_name_raw,
        r.offer_commune_code as job_offer_commune_code,
        r.offer_naf_code as naf_code_on_offer,
        r.match_status as match_status,

        r.company.siren as siren,
        r.company.headquarters_siret as siret_headquarters,
        r.company.full_name as company_legal_name,
        r.company.naf_code as company_naf_code,
        r.company.naf_section as company_naf_section,
        r.company.employee_count_range as employee_count_range,
        r.company.employee_count_reference_year as employee_count_reference_year,
        r.company.company_category as company_category,
        r.company.creation_date::date as company_creation_date,
        r.company.establishment_count::integer as establishment_count,
        r.company.headquarters_commune as headquarters_city,
        r.company.headquarters_postal_code as headquarters_postal_code

    from unnested

)

select * from renamed
