{{ config(materialized='table') }}

-- dim_rome — référentiel des métiers ROME présents dans le périmètre.
-- Grain : une ligne par code ROME. Clé : rome_code.
-- Alimenté depuis les offres elles-mêmes (et non depuis le référentiel ROME exporté) :
-- la Session 1 a établi que l'export et l'API live peuvent diverger de version.
-- Le périmètre S1 étant hybride (codeROME + motsCles), les codes vont au-delà
-- des deux ciblés explicitement (M1405, M1811).

select distinct
    rome_code,
    rome_libelle

from {{ ref('stg_ft_offres') }}