{{ config(materialized='table') }}

-- dim_commune: geographic reference table for the scope.
-- Grain: one row per geographic key. Key: commune_key.
--
-- WHY THE KEY IS NO LONGER THE POSTAL CODE. Paris, Lyon and Marseille are
-- the three French communes with arrondissements: they have no single
-- postal code, so France Travail returns their overall commune's INSEE code
-- (75056, 69123, 13055) with an EMPTY postal code. Indexed on postal code
-- alone, this dimension therefore systematically missed the country's three
-- largest cities. Measured 2026-09-04: 95 offers affected, 77 of them in
-- Paris: the report showed 71 Parisian offers where there are actually 148.
-- Geographic coverage goes from 79.6% to 89.5% of the corpus.
--
-- It's a lesson already learned that repeats itself: what was assumed
-- (postal code) didn't match reality (INSEE code). The same fix had
-- already been applied to the company enrichment and never carried over to
-- the geographic dimension.
--
-- postal_code and commune_code stay exposed alongside the key: they let you
-- audit which of the two sources supplied the value.

with keys as (

    select
        coalesce(postal_code, commune_code) as commune_key,
        postal_code,
        commune_code
    from {{ ref('stg_raw__ft_job_offers') }}
    where coalesce(postal_code, commune_code) is not null

    -- A postal code can cover several INSEE communes: a select distinct on
    -- the pair would then produce two rows for the same key and break the
    -- grain. That's exactly the trap already hit (196 rows instead of 193).
    -- qualify decides on the key itself, never on the pair.
    qualify row_number() over (
        partition by coalesce(postal_code, commune_code)
        order by postal_code nulls last, commune_code
    ) = 1

)

select
    k.commune_key,
    k.postal_code,
    k.commune_code,
    m.commune_name
from keys as k
left join {{ ref('mapping_communes') }} as m
    on m.commune_key = k.commune_key
