-- Staging du dump d'extraction LLM (Phase 4).
-- Grain : 1 ligne = 1 offre. Les listes technologies/domaines restent des
-- colonnes de type LIST à ce stade : l'aplatissement en 1 ligne par couple
-- (offre, terme) est une transformation de modélisation, donc du ressort des
-- marts, pas du staging (règle §7.2 : aucune logique métier ici).
select
    t.r.offre_id as offre_id,
    t.r.statut_extraction as statut_extraction,
    t.r.erreur as erreur,
    t.r.technologies as technologies,
    t.r.domaines as domaines,
    t.r.niveau_etudes as niveau_etudes,
    t.r.annees_experience_min::integer as annees_experience_min,
    t.r.teletravail as teletravail,
    t.r.anglais_requis::boolean as anglais_requis,
    t.r.salaire_texte as salaire_texte,
    t.r.entreprise_nom_texte as entreprise_nom_texte,
    t.r.client_final_masque::boolean as client_final_masque

from {{ source('extraction', 'extraction_skills') }} as s,
    unnest(s.resultats) as t(r)