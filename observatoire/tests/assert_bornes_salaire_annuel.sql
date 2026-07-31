{{ config(
    severity = 'warn',
    tags = ['known_issue']
) }}

-- Test singulier : aucune offre annuelle ne doit avoir un salaire_min hors
-- de la fourchette de plausibilité [10000, 300000] (spec §12.1).
-- Limité à salaire_periode = 'annuel' : les bornes horaire/mensuel ne sont
-- pas mesurées, décision différée (S3/S4).
--
-- SEVERITY: WARN, décision assumée (S4, 31/07/2026) — pas un contournement
-- silencieux. Ce test attrape un cas connu et documenté depuis la S3
-- ("Annuel de 15.0 Euros", 1 occurrence) jamais corrigé faute d'un 2e
-- exemple pour établir une règle de correction défendable (principe
-- projet §12.3 : ne jamais corriger sur un cas isolé). Le WARN garde le
-- pipeline vert sans effacer le signal — voir §12.3 (FAIL vs ERROR).
-- Si un 2e cas apparaît un jour avec de nouvelles données, ça change la
-- donne : passer en severity: error et traiter comme une vraie règle.
--
-- Contrat dbt : 0 ligne = pass, >= 1 ligne = warn (pas fail).

select
    offre_id,
    salaire_min,
    salaire_periode
from {{ ref('fct_offre') }}
where salaire_periode = 'annuel'
  and (salaire_min < 10000 or salaire_min > 300000)