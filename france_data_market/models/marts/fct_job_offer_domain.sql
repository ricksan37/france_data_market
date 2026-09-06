{{ config(materialized='table') }}
-- Table de faits, grain fin : 1 ligne = 1 couple (offre, domaine).
-- Modèle distinct de fct_offre_technologie plutôt qu'une table unique avec
-- une colonne type_skill : décision explicite. Coût assumé : une
-- question portant sur tous les termes confondus demandera un union all.
--
-- LIMITE CONNUE : le modèle d'extraction (mistral-nemo) sous-extrait ce
-- champ sur les annonces de conseil. Les comptages de domaines sont donc
-- des planchers, pas des mesures exactes. Voir extraction_skills.py.
--
-- NORMALISATION : sur les 552 offres réelles, 1473 valeurs de domaine
-- distinctes pour 3489 mentions : fragmentation lexicale (casse, langue,
-- sigles : "BI"/"Business Intelligence", "Data Governance"/"gouvernance des
-- données") qui rend le champ brut inexploitable pour un group by. Un
-- mapping (seeds/mapping_domaines.csv) normalise les 12 clusters les plus
-- fréquents (>60 occurrences cumulées chacun) vers une forme canonique.
-- La longue traîne (valeurs à 1-10 occurrences) N'EST PAS mappée : pas de
-- règle construite sur un échantillon trop mince (principe du projet,
-- cf. assert_bornes_salaire_annuel). domaine_brut reste la source d'audit ;
-- domaine_normalise vaut domaine_brut inchangé si aucune correspondance
-- n'existe dans le mapping.
select
    d.offre_id,
    d.domaine as domaine_brut,
    coalesce(m.domaine_canonique, d.domaine) as domaine_normalise
from (
    select
        offre_id,
        unnest(domaines) as domaine
    from {{ ref('stg_offres_skills') }}
    where statut_extraction = 'ok'
) as d
left join {{ ref('mapping_domaines') }} as m
    on d.domaine = m.variante