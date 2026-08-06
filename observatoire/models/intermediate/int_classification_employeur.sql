select
    s.offre_id,
    -- Note : pas de IN(...) ici. Ce moteur DuckDB (1.5.4) plante avec un
    -- INTERNAL Error ("index 4 within vector of size 4") dès qu'une vue
    -- contenant un IN() à plusieurs valeurs est interrogée (GROUP BY, JOIN,
    -- WHERE...), même bug d'optimiseur que celui du point 0 (accepted_values,
    -- NOT IN). Contournement généralisé : chaînes de = / OR.
    case
        when s.code_naf = '62.02A'
            or s.code_naf = '78.20Z'
            or s.code_naf = '78.10Z'
            or s.code_naf = '70.22Z'
            or s.entreprise_nom = 'Michael Page'
            or s.entreprise_nom = 'Fed Group'
            or s.entreprise_nom = 'NEXTGEN RH'
            or s.entreprise_nom = 'STEP UP'
            or s.entreprise_nom = 'Mercato de l''emploi'
            or s.entreprise_nom = 'Externatic'
            or s.entreprise_nom = 'Capgemini'
            or s.entreprise_nom = 'Accenture'
            or s.entreprise_nom = 'CGI'
            or s.entreprise_nom = 'Sopra Steria'
            or s.entreprise_nom = 'Astek'
            or s.entreprise_nom = 'Akkodis'
            or s.entreprise_nom = 'Amaris'
            or s.entreprise_nom = 'Alteca'
            or s.entreprise_nom = 'Randstad professional'
            or s.entreprise_nom = 'ADECCO'
            or s.entreprise_nom = 'CRIT INTERIM'
            then 'INTERMEDIAIRE'
        when s.entreprise_nom is not null then 'EMPLOYEUR_DIRECT'
        -- Reclassification Phase 4 : offres sans NAF/nom exploitable (donc
        -- ANONYME par le critère structurel), mais où le texte de l'offre
        -- révèle explicitement que l'annonceur agit pour un client masqué
        -- (client_final_masque, extrait par LLM sur la description).
        -- Statut distinct plutôt que fusion dans 'INTERMEDIAIRE' : même
        -- principe que match_consolide_groupe_* en Phase 3, pour tracer et
        -- filtrer en aval sans corriger silencieusement une catégorie
        -- construite sur un critère différent (texte libre vs NAF/nom
        -- structurés).
        when k.client_final_masque = true then 'INTERMEDIAIRE_reclasse'
        else 'ANONYME'
    end as categorie_employeur
from {{ ref('stg_ft_offres') }} s
left join {{ ref('stg_offres_skills') }} k
    on s.offre_id = k.offre_id