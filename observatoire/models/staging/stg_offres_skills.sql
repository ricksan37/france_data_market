-- Staging du dump d'extraction LLM (Phase 4).
-- Grain : 1 ligne = 1 offre. Les listes technologies/domaines restent des
-- colonnes de type LIST à ce stade : l'aplatissement en 1 ligne par couple
-- (offre, terme) est une transformation de modélisation, donc du ressort des
-- marts, pas du staging (règle §7.2 : aucune logique métier ici).
--
-- Branche conditionnelle (Session 7) : en CI (CI_SANS_EXTRACTION=true), le
-- dump d'extraction n'existe pas -- Ollama tourne 3h en local, jamais sur un
-- runner GitHub. Le modèle renvoie alors 0 ligne avec le même schéma, plutôt
-- que d'échouer à la lecture d'un fichier absent. int_classification_employeur
-- dégrade déjà proprement sur une table vide (client_final_masque toujours
-- NULL -> jamais de branche INTERMEDIAIRE_reclasse en CI, comportement voulu).
{% if not en_ci_sans_extraction() %}
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
{% else %}
select
    cast(null as varchar) as offre_id,
    cast(null as varchar) as statut_extraction,
    cast(null as json) as erreur,
    cast(null as varchar[]) as technologies,
    cast(null as varchar[]) as domaines,
    cast(null as varchar) as niveau_etudes,
    cast(null as integer) as annees_experience_min,
    cast(null as varchar) as teletravail,
    cast(null as boolean) as anglais_requis,
    cast(null as varchar) as salaire_texte,
    cast(null as varchar) as entreprise_nom_texte,
    cast(null as boolean) as client_final_masque
where false
{% endif %}