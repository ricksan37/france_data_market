-- Staging model for the LLM extraction dump.
-- Grain: 1 row = 1 job offer. The technologies/domains lists stay LIST-typed
-- at this stage: flattening into 1 row per (offer, term) is a modeling
-- transformation, so it belongs to the marts, not staging (no business
-- logic here).
--
-- domaines/niveau_etudes/etc. are read from the raw dump under their
-- French key names on purpose: those keys are the JSON schema the LLM
-- (mistral-nemo) is constrained to fill in, and the extraction prompt's
-- per-field instructions are anchored to these exact names. Translating
-- them here, at the boundary, keeps that measured extraction setup
-- untouched while giving the rest of the project English column names.
--
-- Conditional branch: in CI (CI_WITHOUT_EXTRACTION=true), the extraction dump
-- doesn't exist -- Ollama runs for 3h locally, never on a GitHub runner. The
-- model then returns 0 rows with the same schema rather than failing to read
-- an absent file. int_employer_classification already degrades cleanly on
-- an empty table (end_client_masked always NULL -> INTERMEDIARY_RECLASSIFIED
-- branch never triggers in CI, intended behavior).
{% if not in_ci_without_extraction() %}

with source as (

    select * from {{ source('extraction', 'skills') }}

),

unnested as (

    select t.r as r
    from source as s,
        unnest(s.resultats) as t(r)

),

renamed as (

    select
        r.job_offer_id,
        r.extraction_status,
        r.error,
        r.technologies,
        r.domaines as domains,
        r.niveau_etudes as education_level,
        r.annees_experience_min::integer as min_years_experience,
        r.teletravail as remote_work,
        r.anglais_requis::boolean as english_required,
        r.salaire_texte as salary_text,
        r.entreprise_nom_texte as employer_name_text,
        r.client_final_masque::boolean as end_client_masked

    from unnested

)

select * from renamed

{% else %}

select
    cast(null as varchar) as job_offer_id,
    cast(null as varchar) as extraction_status,
    cast(null as json) as error,
    cast(null as varchar[]) as technologies,
    cast(null as varchar[]) as domains,
    cast(null as varchar) as education_level,
    cast(null as integer) as min_years_experience,
    cast(null as varchar) as remote_work,
    cast(null as boolean) as english_required,
    cast(null as varchar) as salary_text,
    cast(null as varchar) as employer_name_text,
    cast(null as boolean) as end_client_masked
where false

{% endif %}
