-- Staging du dump d'enrichissement DINUM.
-- Aucune logique métier ici : aplatissement, renommage, casting. Le grain
-- reste 1 ligne = 1 offre enrichie (213), pas encore 1 ligne = 1 SIREN.
select
    t.r.offre_id as offre_id,
    t.r.entreprise_nom_offre as entreprise_nom_offre,
    t.r.commune_offre as commune_offre,
    t.r.code_naf_offre as code_naf_offre,
    t.r.statut_matching as statut_matching,

    t.r.entreprise.siren as siren,
    t.r.entreprise.siret_siege as siret_siege,
    t.r.entreprise.nom_complet as entreprise_nom_complet,
    t.r.entreprise.code_naf as entreprise_code_naf,
    t.r.entreprise.section_naf as entreprise_section_naf,
    t.r.entreprise.tranche_effectif as tranche_effectif,
    t.r.entreprise.annee_effectif as annee_effectif,
    t.r.entreprise.categorie_entreprise as categorie_entreprise,
    t.r.entreprise.date_creation::date as date_creation,
    t.r.entreprise.nombre_etablissements::integer as nombre_etablissements,
    t.r.entreprise.commune_siege as commune_siege,
    t.r.entreprise.code_postal_siege as code_postal_siege

from {{ source('dinum', 'dinum_entreprises') }} as s,
    unnest(s.resultats) as t(r)