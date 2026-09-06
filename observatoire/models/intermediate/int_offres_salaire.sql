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
    -- (zone vide 5400-30000€). Décision mesurée, documentée séparément.
    case
        when salaire_periode_brute = 'Mensuel' and salaire_min > 10000 then 'annuel'
        else lower(salaire_periode_brute)
    end as salaire_periode,
    salaire_periode_brute,
    salaire_min,
    coalesce(salaire_max_brut, salaire_min) as salaire_max,
    salaire_libelle is not null as salaire_mentionne,

    -- Plausibilite du montant annuel, bornes [10000, 300000] (spec §12.1).
    -- NULL quand la question ne se pose pas : periode non annuelle, ou aucun
    -- montant. Un booleen a trois etats plutot que deux, parce que "non
    -- applicable" n'est pas "implausible".
    --
    -- POURQUOI UN DRAPEAU ET NON UNE RECLASSIFICATION DE PERIODE. Une mesure
    -- anterieure a reclasse "Mensuel > 10000" en annuel, sur une zone vide de la
    -- distribution. La figure symetrique existe ici : rien entre 1800 et
    -- 25000 EUR, soit 23200 EUR de vide, et les 15 valeurs sous la borne
    -- tombent dans les distributions observees des mensuels (506-4000) et
    -- des horaires (12-25). La tentation etait donc reelle. Mesure du coût,
    -- 03/09 :
    --   - reclasser les 11 offres a 1800 porterait la population mensuelle
    --     de 34 a 45, dont 24 % issues d'UN SEUL annonceur (11 annonces
    --     quasi jumelles, toutes ANONYME, toutes outre-mer, publiees en
    --     six jours), et sa mediane de 2261 a 1900 EUR
    --   - reclasser les 4 offres a 15-40 doublerait la population horaire,
    --     dont la moitie de valeurs nouvelles, et porterait son maximum
    --     observe de 25 a 40 EUR
    --   - le gain cote annuel est NUL : mediane 45000 avec ou sans elles
    -- On abimerait deux petites populations pour ne rien gagner sur la
    -- grande. Le drapeau exclut sans detruire : la valeur reste lisible,
    -- l'agregation l'ignore, et la decision est auditable.
    case
        when salaire_periode_brute is null then null
        when lower(salaire_periode_brute) != 'annuel'
             and not (salaire_periode_brute = 'Mensuel' and salaire_min > 10000)
            then null
        when salaire_min is null then null
        else salaire_min >= 10000 and salaire_min <= 300000
    end as salaire_annuel_plausible
from converti