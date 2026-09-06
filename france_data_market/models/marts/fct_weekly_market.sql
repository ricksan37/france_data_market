{{ config(materialized='table') }}

-- Fait hebdomadaire : etat du corpus d'offres, semaine par semaine.
-- Grain : 1 ligne = 1 semaine ISO (lundi). L'unicite est garantie a la source
-- par l'upsert de snapshot_hebdo.py, et verifiee ici par un test plutot que
-- supposee -- l'ancienne ecriture en append avait produit trois lignes pour la
-- seule semaine du 09/08.
--
-- PORTEE DE LA MESURE, a lire avant d'interpreter une courbe :
-- nb_offres_total compte le CORPUS ACCUMULE (union dedoublonnee de tous les
-- dumps presents sur disque), pas les offres actives sur France Travail cette
-- semaine-la. Une offre de juillet retiree de l'API y reste comptee. Mesurer
-- le flux reel -- apparitions, disparitions -- demande un historique au grain
-- de l'offre, hors de portee d'un fichier d'agregats. Documente ici pour que
-- personne ne lise cette table comme une mesure de marche.
--
-- variation_offres est NULL sur la premiere semaine : l'absence de point de
-- comparaison n'est pas une variation nulle. Meme principe que la cellule vide
-- de nb_intermediaire_reclasse en CI.

with hebdo as (

    select * from {{ ref('stg_marche_hebdo') }}

)

select
    semaine,
    nb_offres_total,
    nb_anonyme,
    nb_intermediaire,
    nb_intermediaire_reclasse,
    nb_employeur_direct,
    salaire_median_annuel,
    top_technologie,
    extraction_llm,

    nb_offres_total - lag(nb_offres_total) over (order by semaine)
        as variation_offres,

    -- nullif : une semaine a zero offre serait une anomalie a diagnostiquer,
    -- pas une raison de faire echouer la construction du mart.
    round(nb_anonyme * 100.0 / nullif(nb_offres_total, 0), 1)
        as taux_anonymat_pct,

    round(nb_employeur_direct * 100.0 / nullif(nb_offres_total, 0), 1)
        as taux_employeur_direct_pct

from hebdo
