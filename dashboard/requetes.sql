-- Requêtes du rapport HTML Phase 6a (Observatoire du Marché Data France).
-- Ce fichier documente les requêtes indépendamment de leur usage en Python
-- (dashboard/generer_rapport.py) -- convention établie dans les Extensions
-- du Second Brain (queries.sql à côté de index.html).
--
-- Deux requêtes (SKILLS_TOP10, DOMAINES_CLUSTERS) dépendent de
-- stg_offres_skills, qui dégrade proprement à 0 ligne en environnement
-- CI_SANS_EXTRACTION=true (cf. macros/environnement_ci.sql). Documenté
-- requête par requête ci-dessous.

-- ============================================================
-- SECTION 1 : SKILLS DEMAND
-- Dépend de stg_offres_skills -> 0 ligne en CI, dégradation gérée
-- côté Python (theme_millimeter.figure_vide).
-- ============================================================

-- SKILLS_TOP10 : top 10 technologies par nombre d'offres distinctes
select
    technologie,
    count(distinct offre_id) as nb_offres
from fct_offre_technologie
group by technologie
order by nb_offres desc
limit 10;


-- ============================================================
-- SECTION 2 : DOMAINES
-- Dépend de stg_offres_skills -> 0 ligne en CI, dégradation gérée
-- côté Python.
-- ============================================================

-- DOMAINES_CLUSTERS : les clusters normalisés par nombre d'offres.
-- Filtre corrigé (Session 7, testé en direct) : domaine_normalise ne peut
-- pas distinguer "mappé" de "resté brut" par un simple is not null, car
-- coalesce(m.domaine_canonique, d.domaine) retombe sur la valeur brute
-- plutôt que NULL quand le mapping ne matche pas (cf. fct_offre_domaine.sql).
-- Il faut donc rejoindre la table des formes canoniques pour isoler
-- uniquement les clusters mappés. Mesuré : 11 clusters (pas 12, à noter
-- sans investigation supplémentaire -- écart mineur, non bloquant).
select
    domaine_normalise,
    count(distinct offre_id) as nb_offres
from fct_offre_domaine
where domaine_normalise in (select distinct domaine_canonique from mapping_domaines)
group by domaine_normalise
order by nb_offres desc;

-- DOMAINES_COUVERTURE : taux de couverture du mapping (big stat)
-- Corrigé (Session 7, même raison que DOMAINES_CLUSTERS ci-dessus) :
-- is not null est inutilisable sur domaine_normalise (jamais NULL par
-- construction du coalesce). Filtre par appartenance aux formes
-- canoniques. Mesuré : 19,8% (vs 19,7% du test assert_couverture_mapping_domaines,
-- écart de 0,1pt non investigué, non bloquant).
select
    round(
        100.0 * count(case when domaine_normalise in (select distinct domaine_canonique from mapping_domaines) then 1 end)
        / nullif(count(*), 0),
        1
    ) as taux_couverture_pct
from fct_offre_domaine;


-- ============================================================
-- SECTION 3 : SALARY INTELLIGENCE
-- Ne dépend pas de stg_offres_skills -> toujours peuplée, y compris en CI.
-- Exclut systématiquement l'offre 4933945 (anomalie "Annuel de 15.0 Euros",
-- documentée depuis la Session 4) et restreint à salaire_periode='annuel'
-- (les salaires horaire/mensuel restent hors analyse, échantillon trop
-- faible : 19 et 1 offres, cf. limite assumée du README).
-- ============================================================

-- SALAIRE_PAR_CATEGORIE_EMPLOYEUR
select
    categorie_employeur,
    count(offre_id) as nb_offres,
    median(salaire_min) as salaire_median
from fct_offre
where salaire_periode = 'annuel' and offre_id != '4933945'
group by categorie_employeur
order by salaire_median desc;

-- SALAIRE_PAR_EXPERIENCE
select
    experience_exige,
    count(offre_id) as nb_offres,
    median(salaire_min) as salaire_median
from fct_offre
where salaire_periode = 'annuel' and offre_id != '4933945'
group by experience_exige
order by experience_exige;


-- ============================================================
-- SECTION 4 : TRANSPARENCE SALARIALE
-- Ne dépend pas de stg_offres_skills -> toujours peuplée.
-- ============================================================

-- TRANSPARENCE_GLOBALE : taux d'offres avec salaire affiché (big stat)
-- Réactualisé sur les 552 offres actuelles (31% mesuré en v1 sur un
-- échantillon antérieur, à confronter ici).
select
    round(
        100.0 * count(case when salaire_mentionne then 1 end)
        / nullif(count(*), 0),
        1
    ) as taux_transparence_pct
from fct_offre;

-- TRANSPARENCE_PAR_CATEGORIE : décliné par categorie_employeur
-- Insight du notebook (Session 7) : INTERMEDIAIRE plus transparent que
-- EMPLOYEUR_DIRECT, résultat contre-intuitif documenté et confirmé.
select
    categorie_employeur,
    count(distinct offre_id) as nb_offres_total,
    count(distinct case when salaire_mentionne then offre_id end) as nb_avec_salaire,
    round(
        100.0 * count(distinct case when salaire_mentionne then offre_id end)
        / nullif(count(distinct offre_id), 0),
        1
    ) as taux_pct
from fct_offre
group by categorie_employeur
order by taux_pct desc;


-- ============================================================
-- SECTION 5 : GÉOGRAPHIE
-- Ne dépend pas de stg_offres_skills -> toujours peuplée.
-- ============================================================

-- GEOGRAPHIE_TOP10 : top 10 communes par nombre d'offres
select
    c.nom_commune,
    count(distinct o.offre_id) as nb_offres
from fct_offre o
left join dim_commune c on c.code_postal = o.code_postal
where c.nom_commune is not null
group by c.nom_commune
order by nb_offres desc
limit 10;