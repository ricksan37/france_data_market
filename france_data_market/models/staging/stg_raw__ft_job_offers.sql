-- Staging model for the France Travail job offer dumps.
-- Only the most recent dump is kept, so downstream models describe the
-- market as of the latest pull; offer_presence.py keeps the history by
-- reading every dump directly. Dump filenames end with a YYYY-MM-DD_HHMM
-- timestamp, so the greatest filename is the latest pull.
-- Deduplication on job_offer_id is a guard: in a ROME-only dump an offer
-- appears once, since it has a single ROME code. Dumps collected before
-- 2026-09-29 (ROME codes plus keywords) repeat offers matched by several
-- categories: 138 identical copies out of 992 rows in the 2026-09-26 dump.
-- No other business logic here.

with source as (

    select * from {{ source('raw', 'ft_job_offers') }}

),

latest_dump as (

    select *
    from source
    where filename = (select max(filename) from source)

),

unnested as (

    select t.offre as offre
    from latest_dump,
        unnest(resultats) as t(offre)

),

renamed as (

    select
        offre.id as job_offer_id,
        offre.intitule as job_title,
        offre.dateCreation::timestamp as job_offer_creation_date,
        offre.dateActualisation::timestamp as job_offer_last_updated_date,
        offre.romeCode as rome_code,
        offre.romeLibelle as rome_label,
        offre.typeContrat as contract_type,
        offre.experienceExige as required_experience,
        offre.lieuTravail.codePostal as postal_code,
        offre.lieuTravail.commune as commune_code,
        offre.entreprise.nom as employer_name_raw,
        offre.codeNaf as naf_code_on_offer,
        offre.salaire.libelle as salary_label,
        offre.nombrePostes as position_count,
        offre.description as job_description

    from unnested
    qualify row_number() over (
        partition by job_offer_id order by job_offer_last_updated_date desc
    ) = 1

)

select * from renamed
