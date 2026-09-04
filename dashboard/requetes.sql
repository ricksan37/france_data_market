-- Requêtes du rapport HTML (Observatoire du Marché Data France).
-- Ce fichier documente les requêtes indépendamment de leur usage en Python
-- (dashboard/generer_rapport.py), convention établie dans les Extensions du
-- Second Brain (queries.sql à côté de index.html).
--
-- Deux requêtes seulement dépendent de stg_offres_skills et dégradent à zéro
-- ligne en CI_SANS_EXTRACTION (SECTION 05 et SECTION 06). Toutes les autres,
-- y compris les quatre KPI et la section flux, sont peuplées sur un runner.

-- ============================================================
-- PÉRIMÈTRE ET KPI
-- Aucun de ces chiffres n'est écrit en dur dans le rapport. La version
-- précédente annonçait "552 offres" dans son sous-titre alors que le corpus
-- en comptait 960 : le périmètre était figé à trois endroits du code.
-- ============================================================

-- PERIMETRE : nombre d'offres analysées, affiché en sous-titre et en KPI
select count(*) as n from fct_offre;

-- KPI_TRANSPARENCE : part des offres affichant un salaire
select round(100.0 * count(case when salaire_mentionne then 1 end)
             / nullif(count(*), 0), 1) as pct
from fct_offre;

-- KPI_ANONYMAT : dernière valeur connue du taux d'employeur masqué.
-- Vient de fct_marche_hebdo et non d'un calcul direct sur fct_offre : le KPI
-- doit être le dernier point de la série affichée juste en dessous, sinon
-- les deux chiffres peuvent diverger d'un run à l'autre.
select semaine, nb_offres_total, taux_anonymat_pct
from fct_marche_hebdo
order by semaine;

-- KPI_SORTIES : taux de disparition, dernière semaine où il est mesurable.
-- NULL sur la première semaine enregistrée, faute de point de comparaison :
-- le rapport retombe alors sur "N/A" plutôt que d'afficher zéro.
select semaine, semaines_depuis_precedente, nb_actives,
       nb_nouvelles, nb_sorties, taux_sortie_pct
from fct_marche_flux
order by semaine;

-- ============================================================
-- SECTION 01 : FLUX DU MARCHÉ
-- Mesuré sur fct_marche_flux, donc sur la présence réelle des offres dans
-- chaque collecte. Le mesurer sur fct_offre serait faux : le corpus cumule
-- les dumps et ne décroît jamais (960 offres au 31/08, dont 463 avaient déjà
-- disparu de France Travail).
-- ============================================================
-- Les deux requêtes sont celles des KPI ci-dessus, réutilisées telles quelles.

-- ============================================================
-- SECTION 02 : RÉMUNÉRATION
-- Filtre sur salaire_annuel_plausible, pas sur un offre_id écrit en dur.
-- La version précédente excluait nommément l'offre 4933945, seul cas connu
-- en Session 4. Au 03/09 il y en a 15, en deux mécanismes : un salaire
-- mensuel étiqueté annuel (11 annonces à 1800 €, un seul annonceur) et un
-- taux horaire étiqueté annuel (4 annonces, 15 à 40 €). Une exclusion
-- nominative ne passe pas à l'échelle, une règle si.
--
-- L'effectif est remonté avec la médiane et affiché sur chaque barre. Sous
-- 10 offres la catégorie est écartée du graphique et nommée en note :
-- INTERMEDIAIRE_reclasse affichait 65 000 € en tête, calculés sur 3 offres.
-- ============================================================

-- SALAIRE_PAR_CATEGORIE
select categorie_employeur,
       count(*) as n,
       median(salaire_min) as salaire_median
from fct_offre
where salaire_periode = 'annuel' and salaire_annuel_plausible
group by categorie_employeur
order by salaire_median desc;

-- SALAIRE_PAR_EXPERIENCE
-- experience_exige porte les codes bruts France Travail. Mesure du 31/08 :
-- seules D et E sont présentes (540 et 420 offres), S est absente. La
-- traduction en libellés lisibles vit dans le générateur, jamais ici ni dans
-- les modèles dbt, qui gardent les valeurs canoniques.
select experience_exige,
       count(*) as n,
       median(salaire_min) as salaire_median
from fct_offre
where salaire_periode = 'annuel' and salaire_annuel_plausible
group by experience_exige
order by salaire_median;

-- ============================================================
-- SECTION 03 : TRANSPARENCE SALARIALE
-- ============================================================

-- TRANSPARENCE_PAR_CATEGORIE
select categorie_employeur,
       round(100.0 * count(distinct case when salaire_mentionne then offre_id end)
             / nullif(count(distinct offre_id), 0), 1) as taux_pct
from fct_offre
group by categorie_employeur
order by taux_pct desc;

-- ============================================================
-- SECTION 04 : GÉOGRAPHIE
-- ============================================================

-- TOP_COMMUNES
select c.nom_commune, count(distinct o.offre_id) as nb_offres
from fct_offre o
left join dim_commune c on c.code_postal = o.code_postal
where c.nom_commune is not null
group by c.nom_commune
order by nb_offres desc
limit 10;

-- ============================================================
-- SECTION 05 : TECHNOLOGIES
-- Dépend de stg_offres_skills, donc zéro ligne en CI. La dégradation est
-- détectée sur le résultat vide et non sur la variable d'environnement :
-- on mesure l'état réel des données plutôt qu'un signal indirect.
-- ============================================================

-- TECHNOLOGIES_TOP10
select technologie, count(distinct offre_id) as nb_offres
from fct_offre_technologie
group by technologie
order by nb_offres desc
limit 10;

-- ============================================================
-- SECTION 06 : DOMAINES
-- Même dépendance que la section 05.
-- ============================================================

-- DOMAINES_CLUSTERS
-- Filtre par appartenance aux formes canoniques, et non par is not null :
-- domaine_normalise n'est jamais NULL, le coalesce de fct_offre_domaine
-- retombe sur la valeur brute quand le mapping ne matche pas.
select domaine_normalise, count(distinct offre_id) as nb_offres
from fct_offre_domaine
where domaine_normalise in (select distinct domaine_canonique from mapping_domaines)
group by domaine_normalise
order by nb_offres desc;

-- DOMAINES_COUVERTURE
-- Mesuré le 31/08 sur 960 offres : 19,7 %, identique au 19,7 % mesuré en
-- Session 6 sur 552 offres. La longue traîne grossit au même rythme que les
-- douze clusters de tête, donc le mapping ne se dilue pas.
select round(100.0 * count(case when domaine_normalise in
             (select distinct domaine_canonique from mapping_domaines)
           then 1 end) / nullif(count(*), 0), 1) as pct
from fct_offre_domaine;
