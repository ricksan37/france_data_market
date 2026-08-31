-- La cle du snapshot est le lundi de la semaine ISO (snapshot_hebdo.py,
-- fonction lundi_de_la_semaine). Une date qui n'est pas un lundi signale un
-- retour a l'ancienne cle -- la date d'execution -- qui avait produit trois
-- lignes distinctes pour la seule semaine du 09/08.
--
-- dayofweek() en DuckDB : 0 = dimanche, 1 = lundi. Comparaison a une seule
-- valeur, donc le bug d'optimiseur de la Session 3 ne s'applique pas ici.

select semaine
from {{ ref('fct_marche_hebdo') }}
where dayofweek(semaine) != 1
