-- Staging model for the France Travail raw job offers dump.
-- Deduplication: qualify row_number() over (partition by job_offer_id order
-- by job_offer_last_updated_date desc) = 1 -- 1094 raw rows -> 552 unique
-- offers (measured, see spec). No other business logic here.

with source as (

    select * from {{ source('raw', 'ft_job_offers') }}

),

unnested as (

    select t.offre as offre
    from source,
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
