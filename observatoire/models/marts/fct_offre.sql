{{ config(materialized='table') }}
-- fct_offre : table de faits, grain fin.
-- Grain : une ligne par offre. Clé : offre_id.
-- Assemble stg_ft_offres (faits bruts) avec les enrichissements des couches int_ :
-- parsing salaire (int_offres_salaire) et classification employeur
-- (int_classification_employeur). Left join depuis stg_ft_offres : la table de faits
-- ne doit jamais perdre de lignes à cause d'un enrichissement absent ou en retard.
-- rome_code et code_postal restent en clés étrangères brutes vers dim_rome /
-- dim_commune (pas de jointure ici, voir tests relationships, point 6).
--
-- entreprise_nom : par défaut la valeur structurée France Travail (fiable à
-- 100 %). Scopée uniquement sur categorie_employeur = 'INTERMEDIAIRE_reclasse'
-- (21 offres), elle est remplacée par entreprise_nom_texte, extrait
-- par LLM depuis le corps de l'offre. Le scope est volontairement restreint à
-- ce seul statut : c'est justement la colonne qui trace qu'une valeur vient du
-- texte plutôt que du champ structuré, donc pas de mélange silencieux : un nom
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

    -- Clé géographique unifiée : le code postal quand il existe, le code INSEE
    -- sinon. Voir dim_commune pour le pourquoi (Paris, Lyon et Marseille n'ont
    -- pas de code postal unique et arrivent sans).
    coalesce(f.code_postal, f.commune) as cle_commune,

    -- Zone plutôt que restriction de périmètre. La question « et si on se
    -- limitait à la métropole ? » a été mesurée le 04/09 : l'outre-mer pèse 17
    -- offres sur 960, et l'exclure ne déplace aucune métrique (employeur masqué
    -- 33,6 -> 33,0 %, médiane salariale identique). Restreindre coûterait la
    -- perte de 5 employeurs réels et distincts, sans rien gagner. La zone est
    -- donc exposée comme dimension : filtrer devient une clause d'une ligne,
    -- disponible à la demande, sans toucher à la spec ni jeter de données.
    -- Comparaisons chaînées et non IN() : bug d'optimiseur DuckDB connu.
    case
        when coalesce(f.code_postal, f.commune) is null then 'inconnue'
        when substr(coalesce(f.code_postal, f.commune), 1, 2) = '97'
          or substr(coalesce(f.code_postal, f.commune), 1, 2) = '98'
            then 'outre-mer'
        else 'metropole'
    end as zone_geographique,
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
    s.salaire_annuel_plausible,

    -- Grappes d'annonces identiques. Voir int_grappes_annonces : un même poste
    -- publié dans plusieurs villes reçoit un identifiant par ville et compte
    -- donc autant de fois dans tous les agrégats. Filtrer sur
    -- est_annonce_canonique compte des annonces, ne pas filtrer compte des
    -- offres. Les deux questions sont légitimes.
    g.signature_annonce,
    g.taille_grappe,
    g.est_annonce_canonique,
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
left join {{ ref('int_grappes_annonces') }} as g
    on f.offre_id = g.offre_id