{{ config(
    severity = 'warn',
    tags = ['known_issue']
) }}

-- Mesure la couverture du mapping de normalisation des domaines
-- (seeds/mapping_domaines.csv), pour détecter une dérive plutôt que de la
-- découvrir silencieusement quand de nouvelles données arriveront (Phase 5).
--
-- Le mapping actuel couvre ~20% des mentions (les 12 clusters de tête,
-- mesurés le 02/08/2026 sur les 552 offres réelles). Ce test n'échoue jamais
-- (WARN uniquement) : son rôle est d'informer, pas de bloquer. Si le taux de
-- couverture chute nettement en dessous de ce niveau avec de nouvelles
-- données, c'est le signal qu'il faut retravailler le mapping : nouveaux
-- clusters apparus, ou volume qui dilue les 12 existants.
--
-- Implémenté comme un test qui échoue TOUJOURS avec le chiffre en message :
-- dbt n'a pas de mécanisme natif pour "afficher une métrique sans échouer",
-- donc on détourne le WARN comme canal d'information périodique.
select
    count(*) as total_mentions,
    count(case when domaine_brut != domaine_normalise
               or domaine_brut in (select variante from {{ ref('mapping_domaines') }})
          then 1 end) as mentions_couvertes,
    round(100.0 * count(case when domaine_brut != domaine_normalise
               or domaine_brut in (select variante from {{ ref('mapping_domaines') }})
          then 1 end) / count(*), 1) as taux_couverture_pct
from {{ ref('fct_offre_domaine') }}
having taux_couverture_pct is not null  -- toujours vrai : force le WARN à chaque run