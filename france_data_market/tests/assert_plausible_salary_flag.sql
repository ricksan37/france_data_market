-- Coherence du drapeau salaire_annuel_plausible avec les bornes qu'il resume.
--
-- SEVERITY: ERROR, et c'est le changement de doctrine du 03/09. Jusqu'ici le
-- seul garde-fou sur les salaires aberrants etait assert_bornes_salaire_annuel,
-- en warn : il comptait le probleme a chaque run sans que personne ne
-- consomme le signal, et les agregations continuaient a l'ingerer. Le drapeau
-- devient la regle ; ce test protege la regle, donc il bloque.
--
-- Trois facons de le casser, toutes attrapees ici :
--   1. drapeau vrai sur une valeur hors bornes
--   2. drapeau faux sur une valeur dans les bornes
--   3. drapeau absent alors que la question se pose (periode annuelle et
--      montant renseigne) -- le cas le plus insidieux, parce qu'un NULL
--      disparait silencieusement de tout filtre `where salaire_annuel_plausible`
--
-- Le troisieme point est la lecon de assert_conservation_flux, deux jours plus
-- tot : un NULL non traite ne fait pas echouer un test, il le fait passer.

select
    offre_id,
    salaire_periode,
    salaire_min,
    salaire_annuel_plausible
from {{ ref('fct_offre') }}
where
    -- 1 et 2 : le drapeau ne dit pas ce que disent les bornes
    (
        salaire_annuel_plausible is not null
        and salaire_annuel_plausible != (salaire_min >= 10000 and salaire_min <= 300000)
    )
    -- 3 : la question se pose et le drapeau ne repond pas
    or (
        salaire_annuel_plausible is null
        and salaire_periode = 'annuel'
        and salaire_min is not null
    )
