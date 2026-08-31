{{ config(materialized='table') }}

-- Flux hebdomadaire du marche : ce qui apparait, ce qui disparait.
-- Grain : 1 ligne = 1 semaine effectivement enregistree.
--
-- POURQUOI CETTE TABLE EXISTE A COTE DE fct_marche_hebdo. Celle-la mesure le
-- CORPUS ACCUMULE, qui ne decroit jamais : une offre vue une fois y reste pour
-- toujours. Mesure du 31/08 : sur les 552 offres de juillet, 463 avaient
-- disparu de France Travail, et fct_offre les comptait toujours. Le flux se
-- mesure donc sur la presence reelle dans chaque pull, jamais sur le cumul.
--
-- LIRE LES TAUX AVEC semaines_depuis_precedente. Les deux premieres semaines
-- enregistrees sont separees de six semaines, pas d'une : un taux de sortie de
-- 83,9 % y couvre une periode de six semaines. Exposer l'ecart plutot que de
-- normaliser d'office laisse le choix a l'analyse, et rend impossible de lire
-- ce chiffre comme un rythme hebdomadaire par inadvertance.
--
-- REAPPARITIONS. nb_nouvelles compte les offres jamais vues auparavant
-- (min(semaine) = t). Une offre presente en juillet, absente en aout, puis
-- republiee n'est donc ni une nouvelle ni une survivante : elle entre dans
-- les actives sans figurer dans le bilan. Le defaut n'etait pas observable
-- sur deux semaines, ou toute offre absente de la premiere est forcement
-- nouvelle ; il est apparu au troisieme point, en CI, et assert_conservation_flux
-- l'a attrape. nb_reapparues ferme le bilan sans denaturer nb_nouvelles, qui
-- garde son sens de marche : une offre reellement neuve.
--
-- nb_sorties, nb_reapparues et taux_sortie_pct sont NULL sur la premiere
-- semaine : aucune semaine anterieure a laquelle comparer. Une absence de
-- comparaison n'est pas une sortie nulle -- meme principe que
-- variation_offres dans fct_marche_hebdo. nb_nouvelles, lui, vaut 0 et non
-- NULL quand aucune offre neuve n'apparait : la mesure a bien ete faite.

with presence as (

    select * from {{ ref('stg_presence_offres') }}

),

-- Les semaines REELLEMENT enregistrees, pas un calendrier continu : un run
-- manque laisse un trou, que semaines_depuis_precedente rend visible.
semaines as (

    select distinct semaine from presence

),

ordre as (

    select
        semaine,
        lag(semaine) over (order by semaine) as semaine_precedente
    from semaines

),

premiere_vue as (

    select
        offre_id,
        min(semaine) as semaine_premiere_vue
    from presence
    group by offre_id

),

actives as (

    select semaine, count(*) as nb_actives
    from presence
    group by semaine

),

nouvelles as (

    select semaine_premiere_vue as semaine, count(*) as nb_nouvelles
    from premiere_vue
    group by 1

),

-- Sorties : presentes la semaine enregistree precedente, absentes celle-ci.
-- Anti-jointure par left join + is null plutot que par NOT IN : un NOT IN a
-- plusieurs centaines de valeurs fait planter l'optimiseur DuckDB (bug
-- Session 3, version-independant).
sorties as (

    select
        o.semaine,
        count(*) as nb_sorties
    from ordre as o
    inner join presence as precedente
        on precedente.semaine = o.semaine_precedente
    left join presence as courante
        on courante.offre_id = precedente.offre_id
        and courante.semaine = o.semaine
    where courante.offre_id is null
    group by o.semaine

),

-- Reapparues : presentes cette semaine, absentes la precedente, mais deja
-- vues plus tot. Le symetrique exact des sorties.
reapparues as (

    select
        o.semaine,
        count(*) as nb_reapparues
    from ordre as o
    inner join presence as courante
        on courante.semaine = o.semaine
    inner join premiere_vue as pv
        on pv.offre_id = courante.offre_id
    left join presence as precedente
        on precedente.offre_id = courante.offre_id
        and precedente.semaine = o.semaine_precedente
    where precedente.offre_id is null
      and pv.semaine_premiere_vue < o.semaine
    group by o.semaine

)

select
    o.semaine,
    date_diff('week', o.semaine_precedente, o.semaine)
        as semaines_depuis_precedente,
    a.nb_actives,

    -- 0 et non NULL : une semaine sans offre neuve est une mesure, pas une
    -- absence de mesure.
    coalesce(n.nb_nouvelles, 0) as nb_nouvelles,

    -- NULL sur la premiere semaine seulement, 0 ensuite.
    case when o.semaine_precedente is null then null
         else coalesce(s.nb_sorties, 0) end as nb_sorties,
    case when o.semaine_precedente is null then null
         else coalesce(r.nb_reapparues, 0) end as nb_reapparues,

    round(100.0 * coalesce(n.nb_nouvelles, 0) / nullif(a.nb_actives, 0), 1)
        as taux_renouvellement_pct,

    -- Rapporte aux actives de la semaine PRECEDENTE : une sortie se mesure sur
    -- la population qui pouvait sortir, pas sur celle qui reste.
    --
    -- Meme coalesce que la colonne nb_sorties, et pour la meme raison : la CTE
    -- ne produit aucune ligne quand personne ne sort, et lire sa valeur brute
    -- affichait NULL la ou le taux vaut 0,0 %. Une semaine sans depart est une
    -- mesure, pas une absence de mesure ; seule la premiere semaine reste NULL.
    case when o.semaine_precedente is null then null
         else round(100.0 * coalesce(s.nb_sorties, 0)
                    / nullif(lag(a.nb_actives) over (order by o.semaine), 0), 1)
    end as taux_sortie_pct

from ordre as o
inner join actives as a on a.semaine = o.semaine
left join nouvelles as n on n.semaine = o.semaine
left join sorties as s on s.semaine = o.semaine
left join reapparues as r on r.semaine = o.semaine
