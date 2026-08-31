-- Staging du snapshot hebdomadaire (Phase 5, spec §13.1).
-- Grain : 1 ligne = 1 semaine ISO, identifiee par le lundi de cette semaine.
-- Aucune logique metier ici (regle §7.2) : typage explicite, rien d'autre.
--
-- Pourquoi caster plutot que laisser faire read_csv_auto : la colonne
-- nb_intermediaire_reclasse est vide sur toutes les semaines produites en CI
-- (la reclassification depend des champs d'extraction LLM, absents du runner).
-- Le type infere d'une colonne entierement vide depend des lignes presentes au
-- moment du run -- il changerait donc au fil des semaines. Un cast explicite
-- fige le contrat du modele independamment du contenu du fichier.

select
    semaine::date as semaine,
    nb_offres_total::integer as nb_offres_total,
    nb_anonyme::integer as nb_anonyme,
    nb_intermediaire::integer as nb_intermediaire,
    nb_intermediaire_reclasse::integer as nb_intermediaire_reclasse,
    nb_employeur_direct::integer as nb_employeur_direct,
    salaire_median_annuel::double as salaire_median_annuel,
    top_technologie::varchar as top_technologie,
    extraction_llm::boolean as extraction_llm
from {{ source('historique', 'marche_hebdo') }}
