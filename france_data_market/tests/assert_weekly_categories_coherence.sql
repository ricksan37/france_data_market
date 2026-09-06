-- Les quatre categories d'employeur partitionnent les offres : leur somme doit
-- retomber exactement sur nb_offres_total. Un ecart signale soit une categorie
-- apparue sans etre reportee dans snapshot_hebdo.py, soit un decompte fausse.
--
-- coalesce sur nb_intermediaire_reclasse : la colonne est vide (et non zero)
-- sur les semaines CI, et NULL + 918 vaut NULL -- le test passerait alors en
-- silence au lieu d'echouer, exactement le genre de faux negatif qu'on cherche
-- a eviter.
--
-- Verifie a la main sur les trois semaines existantes avant d'ecrire ce test :
-- 314+197+407 = 918, 335+205+420 = 960, 348+185+425 = 958. Les trois tombent.

select semaine
from {{ ref('fct_marche_hebdo') }}
where nb_anonyme
    + nb_intermediaire
    + coalesce(nb_intermediaire_reclasse, 0)
    + nb_employeur_direct
  != nb_offres_total
