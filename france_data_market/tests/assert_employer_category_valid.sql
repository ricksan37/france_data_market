-- Test singulier : categorie_employeur ne doit jamais sortir d'une valeur
-- hors des 4 catégories connues. Comme pour type_contrat, on évite
-- accepted_values / IN / NOT IN qui déclenchent le bug d'optimiseur DuckDB
-- 1.5.4 (INTERNAL Error: index 4 within vector of size 4).
-- Contrat dbt : 0 ligne = pass, >= 1 ligne = fail.
select
    offre_id,
    categorie_employeur
from {{ ref('int_classification_employeur') }}
where categorie_employeur != 'EMPLOYEUR_DIRECT'
  and categorie_employeur != 'INTERMEDIAIRE'
  and categorie_employeur != 'ANONYME'
  and categorie_employeur != 'INTERMEDIAIRE_reclasse'