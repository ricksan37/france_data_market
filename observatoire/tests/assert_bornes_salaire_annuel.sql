{{ config(
    severity = 'warn',
    tags = ['known_issue']
) }}

-- Test singulier : aucune offre annuelle ne doit avoir un salaire_min hors
-- de la fourchette de plausibilité [10000, 300000] (spec §12.1).
-- Limité à salaire_periode = 'annuel' : les bornes horaire/mensuel ne sont
-- pas mesurées, décision différée.
--
-- SEVERITY: WARN, et ce test reste volontairement un COMPTEUR. Il mesure
-- combien de valeurs aberrantes existent ; il n'a jamais eu vocation à les
-- écarter d'une agrégation.
--
-- La condition posée précédemment est remplie. Elle disait : « si un 2e cas
-- apparaît un jour avec de nouvelles données, ça change la donne ». Au
-- 03/09/2026, sur 960 offres, il y en a 15, réparties en quatre sources
-- distinctes et deux mécanismes cohérents : un salaire mensuel étiqueté
-- annuel (11 annonces d'un même annonceur, toutes à 1800 €) et un taux
-- horaire étiqueté annuel (4 annonces, 15 à 40 €). La règle a donc été
-- écrite, mais ailleurs : salaire_annuel_plausible dans
-- int_offres_salaire, protégé par assert_flag_salaire_plausible en
-- severity error.
--
-- Pourquoi ce test-ci ne passe pas en error pour autant : les 15 lignes
-- existent et continueront d'exister, puisqu'on a choisi de les marquer
-- plutôt que de les corriger. Le faire échouer bloquerait le pipeline sur
-- un état connu et assumé. Son WARN garde le compte visible à chaque run,
-- ce qui reste utile : si le nombre s'envole, la source a changé.
--
-- Contrat dbt : 0 ligne = pass, >= 1 ligne = warn (pas fail).

select
    offre_id,
    salaire_min,
    salaire_periode
from {{ ref('fct_offre') }}
where salaire_periode = 'annuel'
  and (salaire_min < 10000 or salaire_min > 300000)