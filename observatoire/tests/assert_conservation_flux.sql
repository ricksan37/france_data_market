-- Conservation du flux : les actives d'une semaine doivent etre exactement les
-- actives de la semaine precedente, moins les sorties, plus les nouvelles,
-- plus les reapparues.
--
--   552 - 463 + 408 + 0 = 497   (les deux premieres semaines mesurees)
--
-- C'est le test le plus fort du modele de flux : il relie quatre mesures
-- calculees independamment (une agregation, une premiere occurrence, deux
-- anti-jointures symetriques). Si l'une derive, l'egalite casse.
--
-- Il a deja servi. Le terme nb_reapparues manquait a la premiere version :
-- une offre republiee apres une absence n'etait ni nouvelle ni survivante et
-- entrait dans les actives sans figurer au bilan. Le defaut etait invisible
-- sur deux semaines et le test l'a fait echouer des le troisieme point, en CI.
--
-- coalesce sur les trois termes : sans lui, un seul NULL rend la comparaison
-- inconnue et le test passe EN SILENCE au lieu d'echouer. C'est arrive dans la
-- meme session sur une semaine sans offre neuve. La premiere semaine reste
-- exclue par la clause sur nb_actives_precedente : sans predecesseur,
-- l'egalite n'a pas de sens.

with flux as (

    select
        semaine,
        nb_actives,
        nb_nouvelles,
        nb_sorties,
        nb_reapparues,
        lag(nb_actives) over (order by semaine) as nb_actives_precedente
    from {{ ref('fct_marche_flux') }}

)

select semaine
from flux
where nb_actives_precedente is not null
  and nb_actives != nb_actives_precedente
                    - coalesce(nb_sorties, 0)
                    + coalesce(nb_nouvelles, 0)
                    + coalesce(nb_reapparues, 0)
