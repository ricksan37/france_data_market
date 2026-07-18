-- Test singulier : aucune offre ne doit avoir un type_contrat hors de la liste connue.
-- NB : on n'utilise NI accepted_values NI NOT IN. Les deux déclenchent un bug
-- interne de l'optimiseur DuckDB 1.5.4 (INTERNAL Error: index 4 within vector
-- of size 4, dans RemoveUnusedColumns/SumRewriterOptimizer). Les != chaînés
-- empruntent un autre chemin de compilation et l'évitent.
-- Contrat dbt : 0 ligne = pass, >= 1 ligne = fail.

select
    offre_id,
    type_contrat
from {{ ref('stg_ft_offres') }}
where type_contrat != 'CDI'
  and type_contrat != 'CDD'
  and type_contrat != 'MIS'
  and type_contrat != 'LIB'
  and type_contrat != 'CCE'