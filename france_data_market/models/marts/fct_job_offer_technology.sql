{{ config(materialized='table') }}

-- Table de faits, grain fin : 1 ligne = 1 couple (offre, technologie).
-- C'est ce grain qui permet de compter combien d'offres demandent Python :
-- un simple group by technologie, impossible sur une colonne LIST.
--
-- Les offres sans aucune technologie (annonces de conseil, ~60 % de
-- l'échantillon testé) DISPARAISSENT ici : unnest sur une liste vide ne
-- produit aucune ligne. Ce n'est pas une perte de donnée : fct_offre reste
-- la table de référence pour le compte d'offres. Ce modèle sert à compter
-- des occurrences de termes, pas des offres.
select
    offre_id,
    unnest(technologies) as technologie
from {{ ref('stg_offres_skills') }}
where statut_extraction = 'ok'