-- Chaque grappe d'annonces identiques a exactement une canonique.
--
-- SEVERITY: ERROR. C'est l'invariant sur lequel repose tout comptage par
-- annonce : zéro canonique ferait disparaître une grappe entière d'un
-- `where est_annonce_canonique`, deux la feraient compter double. Dans les
-- deux cas le total serait faux sans que rien ne le signale.
--
-- Le cas à zéro n'est pas théorique. row_number() ne renvoie 1 pour aucune
-- ligne si la colonne de tri est NULL sur toute la partition et que le moteur
-- ordonne autrement que prévu : c'est le genre de dérive qu'un test attrape et
-- qu'une relecture ne voit pas.

select
    signature_annonce,
    count(*) as taille,
    count(case when est_annonce_canonique then 1 end) as nb_canoniques
from {{ ref('fct_offre') }}
group by signature_annonce
having count(case when est_annonce_canonique then 1 end) != 1
