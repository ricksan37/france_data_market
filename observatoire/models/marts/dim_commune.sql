{{ config(materialized='table') }}

-- dim_commune — référentiel géographique du périmètre.
-- Grain : une ligne par clé géographique. Clé : cle_commune.
--
-- POURQUOI LA CLÉ N'EST PLUS LE CODE POSTAL (Session 9). Paris, Lyon et
-- Marseille sont les trois communes françaises à arrondissements : elles n'ont
-- pas de code postal unique, donc France Travail renvoie leur code INSEE de
-- commune globale (75056, 69123, 13055) avec un code postal VIDE. Indexée sur
-- le seul code postal, cette dimension ratait donc systématiquement les trois
-- plus grandes villes du pays. Mesure du 04/09 : 95 offres concernées, dont 77
-- à Paris — le rapport affichait 71 offres parisiennes là où il y en a 148.
-- La couverture géographique passe de 79,6 % à 89,5 % du corpus.
--
-- C'est la leçon de la Session 5 qui se répète : « la spec disait code postal,
-- les données disaient code INSEE ». Elle avait été appliquée à l'enrichissement
-- entreprise (§7.5) et jamais à la dimension géographique.
--
-- code_postal et commune restent exposés à côté de la clé : ils permettent
-- d'auditer laquelle des deux sources a fourni la valeur.

with cles as (

    select
        coalesce(code_postal, commune) as cle_commune,
        code_postal,
        commune
    from {{ ref('stg_ft_offres') }}
    where coalesce(code_postal, commune) is not null

    -- Un code postal peut couvrir plusieurs communes INSEE : un select distinct
    -- sur le couple produirait alors deux lignes pour une même clé et casserait
    -- le grain. C'est exactement le piège tombé en Session 4 (196 lignes au lieu
    -- de 193). qualify tranche sur la clé elle-même, jamais sur le couple.
    qualify row_number() over (
        partition by coalesce(code_postal, commune)
        order by code_postal nulls last, commune
    ) = 1

)

select
    c.cle_commune,
    c.code_postal,
    c.commune,
    m.nom_commune
from cles as c
left join {{ ref('mapping_communes') }} as m
    on m.cle_commune = c.cle_commune
