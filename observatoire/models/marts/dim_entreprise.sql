{{ config(materialized='table') }}

-- dim_entreprise : grain = 1 SIREN.
-- age_annees est une mesure brute (date_creation -> aujourd'hui), pas un jugement.
-- Volontairement pas de flag is_startup : le triptyque ancienneté + NAF + effectif
-- ne distingue pas fiablement une startup d'une PME quelconque (spec §11), et un
-- seuil figé ici serait une décision cachée dans le mart plutôt qu'une décision
-- visible au moment de l'analyse. Les trois signaux (age_annees, entreprise_code_naf,
-- tranche_effectif) restent séparés pour que le seuil se pose en Phase 6, pas ici.

select 
    siren,
    siret_siege,
    entreprise_nom_complet,
    entreprise_code_naf,
    entreprise_section_naf,
    tranche_effectif,
    annee_effectif,
    categorie_entreprise,
    date_creation,
    date_diff('year', date_creation, current_date) as age_annees,
    nombre_etablissements,
    commune_siege,
    code_postal_siege
from {{ ref('stg_dinum_entreprises') }}
where siren is not null
qualify row_number() over (partition by siren order by offre_id) = 1