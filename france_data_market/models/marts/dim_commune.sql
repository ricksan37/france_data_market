{{ config(materialized='table') }}

-- dim_commune: geographic reference table for the scope.
-- Grain: one row per commune. Key: commune_key, the commune's INSEE code.
--
-- WHY THE INSEE CODE. It is populated on more offers than the postal code
-- (791 vs 584 of 854 on the 2026-09-26 dump), maps 1:1 to a commune, and
-- is the only key Paris, Lyon and Marseille carry (their overall commune,
-- 75056 / 69123 / 13055, has no single postal code). A postal code can
-- cover several communes.
--
-- WHY THE NAME COMES FROM location_label. France Travail already gives
-- "<department> - <commune name>" for every offer with a commune code, so
-- the dimension is complete for any dump, locally and in CI, with no
-- external lookup. The same commune can arrive spelled two ways
-- ("NEUILLY SUR SEINE" / "Neuilly-sur-Seine", 21 of 207 communes): the
-- mixed-case spelling is kept, as it carries accents and hyphens; ties are
-- broken alphabetically so the result doesn't depend on read order.
--
-- ARRONDISSEMENTS. Some Paris, Lyon and Marseille offers carry their
-- arrondissement's INSEE code (75109, "Paris 9e Arrondissement"), others
-- only the overall commune's (75056, "Paris"): 92 vs 208 offers on the
-- 2026-09-26 dump. commune_name is the city in both cases, so grouping by
-- name counts Paris once; the arrondissement stays in arrondissement_name.

with labels as (

    select
        commune_code as commune_key,
        regexp_replace(location_label, '^\S+ - ', '') as full_name
    from {{ ref('stg_raw__ft_job_offers') }}
    where commune_code is not null

),

best_spelling as (

    select
        commune_key,
        full_name
    from labels
    qualify row_number() over (
        partition by commune_key
        order by regexp_matches(full_name, '[a-z]') desc, full_name
    ) = 1

)

select
    commune_key,
    regexp_replace(full_name, ' [0-9]+(er|e) Arrondissement$', '') as commune_name,
    case
        when regexp_matches(full_name, ' [0-9]+(er|e) Arrondissement$') then full_name
    end as arrondissement_name
from best_spelling
