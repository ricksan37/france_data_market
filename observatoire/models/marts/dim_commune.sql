{{ config(materialized='table') }}
-- dim_commune — référentiel des codes postaux présents dans le périmètre.
-- Grain : une ligne par code postal. Clé : code_postal.
-- 19% de codes postaux manquants, dimension qui ne couvre donc pas toutes les offres.
--
-- nom_commune (Session 7) : enrichi depuis seeds/mapping_communes.csv, résolu
-- via l'API publique geo.api.gouv.fr (enrichir_communes.py, scope dynamique
-- et incrémental sur les codes réellement présents dans fct_offre). Left join
-- volontaire : un code postal nouvellement apparu dans un pull futur existe
-- toujours dans cette dimension même avant sa résolution (nom_commune NULL en
-- attendant le prochain lancement du script), jamais de ligne perdue.
-- Valeur 'NON_RESOLU' pour les codes sans correspondance officielle (99999,
-- sentinelle France Travail pour lieu non renseigné ; 13107, coquille de
-- saisie isolée sur 1 offre, cf. exploration Session 7).
select distinct
    s.code_postal,
    s.commune,
    m.nom_commune
from {{ ref('stg_ft_offres') }} as s
left join {{ ref('mapping_communes') }} as m
    on s.code_postal = m.code_postal
where s.code_postal is not null