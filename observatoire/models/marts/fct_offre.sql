{{ config(materialized='table') }}
-- fct_offre — table de faits, grain fin.
-- Grain : une ligne par offre. Clé : offre_id.
-- Assemble stg_ft_offres (faits bruts) avec les enrichissements des couches int_ :
-- parsing salaire (int_offres_salaire) et classification employeur
-- (int_classification_employeur). Left join depuis stg_ft_offres : la table de faits
-- ne doit jamais perdre de lignes à cause d'un enrichissement absent ou en retard.
-- rome_code et code_postal restent en clés étrangères brutes vers dim_rome /
-- dim_commune (pas de jointure ici — voir tests relationships, point 6).
--
-- entreprise_nom : par défaut la valeur structurée France Travail (fiable à
-- 100 %). Scopée uniquement sur categorie_employeur = 'INTERMEDIAIRE_reclasse'
-- (21 offres, Session 7), elle est remplacée par entreprise_nom_texte, extrait
-- par LLM depuis le corps de l'offre. Le scope est volontairement restreint à
-- ce seul statut : c'est justement la colonne qui trace qu'une valeur vient du
-- texte plutôt que du champ structuré, donc pas de mélange silencieux — un nom
-- non structuré n'apparaît que là où le statut le signale déjà.
select
    f.offre_id,
    f.intitule,
    f.date_creation,
    f.date_actualisation,
    f.rome_code,
    f.rome_libelle,
    f.type_contrat,
    f.experience_exige,
    f.code_postal,
    f.commune,
    case
        when c.categorie_employeur = 'INTERMEDIAIRE_reclasse' then k.entreprise_nom_texte
        else f.entreprise_nom
    end as entreprise_nom,
    f.code_naf,
    f.salaire_libelle,
    f.nombre_postes,
    f.description,
    s.salaire_min,
    s.salaire_max,
    s.salaire_periode,
    s.salaire_mentionne,
    c.categorie_employeur,
    d.siren
from {{ ref('stg_ft_offres') }} as f
left join {{ ref('int_offres_salaire') }} as s
    on f.offre_id = s.offre_id
left join {{ ref('int_classification_employeur') }} as c
    on f.offre_id = c.offre_id
left join {{ ref('stg_dinum_entreprises') }} as d
    on f.offre_id = d.offre_id
left join {{ ref('stg_offres_skills') }} as k
    on f.offre_id = k.offre_id