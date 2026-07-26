select
    offre_id,
    -- Note : pas de IN(...) ici. Ce moteur DuckDB (1.5.4) plante avec un
    -- INTERNAL Error ("index 4 within vector of size 4") dès qu'une vue
    -- contenant un IN() à plusieurs valeurs est interrogée (GROUP BY, JOIN,
    -- WHERE...), même bug d'optimiseur que celui du point 0 (accepted_values,
    -- NOT IN). Contournement généralisé : chaînes de = / OR.
    case
        when code_naf = '62.02A'
            or code_naf = '78.20Z'
            or code_naf = '78.10Z'
            or code_naf = '70.22Z'
            or entreprise_nom = 'Michael Page'
            or entreprise_nom = 'Fed Group'
            or entreprise_nom = 'NEXTGEN RH'
            or entreprise_nom = 'STEP UP'
            or entreprise_nom = 'Mercato de l''emploi'
            or entreprise_nom = 'Externatic'
            or entreprise_nom = 'Capgemini'
            or entreprise_nom = 'Accenture'
            or entreprise_nom = 'CGI'
            or entreprise_nom = 'Sopra Steria'
            or entreprise_nom = 'Astek'
            or entreprise_nom = 'Akkodis'
            or entreprise_nom = 'Amaris'
            or entreprise_nom = 'Alteca'
            or entreprise_nom = 'Randstad professional'
            or entreprise_nom = 'ADECCO'
            or entreprise_nom = 'CRIT INTERIM'
            then 'INTERMEDIAIRE'
        when entreprise_nom is not null then 'EMPLOYEUR_DIRECT'
        else 'ANONYME'
    end as categorie_employeur
from {{ ref('stg_ft_offres') }}