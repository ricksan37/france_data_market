{{ config(materialized='table') }}

-- dim_commune — référentiel des codes postaux présents dans le périmètre.
-- Grain : une ligne par code code postal. Clé : code_postal.
-- 19% de codes postaux manquants, dimension qui ne couvre donc pas toutes les offres.
select distinct
    code_postal,
    commune

from {{ ref('stg_ft_offres') }}
where code_postal is not null