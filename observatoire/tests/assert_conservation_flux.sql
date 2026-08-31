-- Conservation du flux : les actives d'une semaine doivent etre exactement les
-- actives de la semaine precedente, moins les sorties, plus les nouvelles.
--
--   552 - 463 + 408 = 497   (verifie a la main sur les deux semaines amorcees)
--
-- C'est le test le plus fort de tout le modele de flux : il relie trois
-- mesures calculees independamment (une agregation, une premiere occurrence,
-- une anti-jointure). Si l'une derive, l'egalite casse. Un simple not_null
-- n'aurait rien attrape.
--
-- La premiere semaine est exclue : sans predecesseur, l'egalite n'a pas de sens.

with flux as (

    select
        semaine,
        nb_actives,
        nb_nouvelles,
        nb_sorties,
        lag(nb_actives) over (order by semaine) as nb_actives_precedente
    from {{ ref('fct_marche_flux') }}

)

select semaine
from flux
where nb_actives_precedente is not null
  and nb_actives != nb_actives_precedente - nb_sorties + nb_nouvelles
