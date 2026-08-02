{{ config(materialized='table') }}

-- Table de faits, grain fin : 1 ligne = 1 couple (offre, domaine).
-- Modèle distinct de fct_offre_technologie plutôt qu'une table unique avec
-- une colonne type_skill : décision explicite (S6). Coût assumé — une
-- question portant sur tous les termes confondus demandera un union all.
--
-- LIMITE CONNUE : le modèle d'extraction (mistral-nemo) sous-extrait ce
-- champ sur les annonces de conseil. Les comptages de domaines sont donc
-- des planchers, pas des mesures exactes. Voir extraction_skills.py.
select
    offre_id,
    unnest(domaines) as domaine
from {{ ref('stg_offres_skills') }}
where statut_extraction = 'ok'