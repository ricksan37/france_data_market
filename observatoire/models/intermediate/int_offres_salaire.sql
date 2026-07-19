with extraction as (

    select
        offre_id,
        salaire_libelle,
        regexp_extract(salaire_libelle, '(Annuel|Mensuel|Horaire) de (\d+(?:\.\d+)?) Euros(?: à (\d+(?:\.\d+)?) Euros)?', 1) as periode_texte,
        regexp_extract(salaire_libelle, '(Annuel|Mensuel|Horaire) de (\d+(?:\.\d+)?) Euros(?: à (\d+(?:\.\d+)?) Euros)?', 2) as montant_1_texte,
        regexp_extract(salaire_libelle, '(Annuel|Mensuel|Horaire) de (\d+(?:\.\d+)?) Euros(?: à (\d+(?:\.\d+)?) Euros)?', 3) as montant_2_texte
    from {{ ref('stg_ft_offres') }}

),

converti as (

    select
        offre_id,
        salaire_libelle,
        periode_texte as salaire_periode_brute,
        cast(cast(nullif(montant_1_texte, '') as double) as integer) as salaire_min,
        cast(cast(nullif(montant_2_texte, '') as double) as integer) as salaire_max_brut
    from extraction

)

select
    offre_id,
    -- Reclassification : un montant "Mensuel" > 10000€ n'est pas plausible comme
    -- salaire mensuel (max observé ~5400€ dans l'échantillon) mais l'est comme
    -- salaire annuel (min observé ~30000€). Aucun cas ambigu entre les deux
    -- (zone vide 5400-30000€). Décision Session 3, voir compte rendu.
    case
        when salaire_periode_brute = 'Mensuel' and salaire_min > 10000 then 'annuel'
        else lower(salaire_periode_brute)
    end as salaire_periode,
    salaire_periode_brute,
    salaire_min,
    coalesce(salaire_max_brut, salaire_min) as salaire_max,
    salaire_libelle is not null as salaire_mentionne
from converti