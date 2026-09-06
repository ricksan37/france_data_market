-- Staging model for the presence history snapshot (Phase 5).
-- Grain: 1 row = 1 (job offer, week it was seen in a pull) pair.
-- No business logic here: explicit typing, nothing else.
--
-- job_offer_id stays varchar: France Travail identifiers have leading zeros
-- (0020136) that a numeric cast would silently destroy.

with source as (

    select * from {{ source('presence', 'job_offer_presence') }}

),

renamed as (

    select
        week_start_date::date as week_start_date,
        job_offer_id::varchar as job_offer_id
    from source

)

select * from renamed
