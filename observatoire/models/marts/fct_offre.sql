{{ config(materialized='table') }}

-- fct_offre — table de faits, grain fin.
-- Grain : une ligne par offre. Clé : offre_id.
-- Assemble stg_ft_offres (faits bruts) avec les enrichissements des couches int_ :
-- parsing salaire (int_offres_salaire) et classification employeur
-- (int_classification_employeur). Left join depuis stg_ft_offres : la table de faits
-- ne doit jamais perdre de lignes à cause d'un enrichissement absent ou en retard.
-- rome_code et code_postal restent en clés étrangères brutes vers dim_rome /
-- dim_commune (pas de jointure ici — voir tests relationships, point 6).

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
    f.entreprise_nom,
    f.code_naf,
    f.salaire_libelle,
    f.nombre_postes,

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