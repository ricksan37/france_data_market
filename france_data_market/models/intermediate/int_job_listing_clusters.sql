-- Regroupement des offres qui sont en réalité la même annonce.
-- Grain : une ligne par offre. Clé : offre_id.
--
-- LE PROBLÈME. Le dédoublonnage de stg_ft_offres travaille sur offre_id : il
-- écarte les doublons d'index de l'API, pas les campagnes. Or un même poste
-- publié dans plusieurs villes reçoit un identifiant par ville, et compte donc
-- autant de fois dans tous les agrégats. Mesure du 04/09 : 152 offres sur 960
-- partagent leur texte avec au moins une autre, soit 15,8 % du corpus. La plus
-- grosse grappe est un employeur qui publie la même annonce dans 24 communes.
--
-- CONSÉQUENCES MESURÉES. SQL passe de 282 à 235 offres (-16,7 %), Python de
-- 283 à 262, et Python repasse nettement devant SQL alors que les deux
-- semblaient au coude-à-coude. La médiane salariale passe de 45 000 à
-- 43 000 €. Ce ne sont pas des ajustements cosmétiques.
--
-- SIGNATURE NORMALISÉE, PAS SEUIL DE SIMILARITÉ. Minuscules et espaces
-- réduits : sept grappes de plus que le texte brut, et surtout aucun seuil à
-- justifier. Deux textes sont identiques ou ils ne le sont pas. Une mesure de
-- similarité attraperait davantage -- sur les onze annonces d'une campagne
-- outre-mer, neuf partagent exactement le même texte et deux en ont un
-- légèrement différent -- mais au prix d'un seuil arbitraire, que ce projet
-- n'introduit pas sans mesure pour le défendre.
-- Risque de fausse grappe écarté par la mesure : la description la plus courte
-- du corpus fait 296 caractères, 17 seulement passent sous 500.
--
-- ON MARQUE, ON NE SUPPRIME PAS. Aucune offre n'est écartée : chaque analyse
-- choisit de compter des offres ou des annonces. Les deux questions sont
-- légitimes et n'ont pas la même réponse.

with signatures as (

    select
        offre_id,
        date_creation,
        md5(lower(regexp_replace(trim(description), '\s+', ' ', 'g')))
            as signature_annonce
    from {{ ref('stg_ft_offres') }}

)

select
    offre_id,
    signature_annonce,
    count(*) over (partition by signature_annonce) as taille_grappe,

    -- La canonique est la PLUS ANCIENNE de la grappe : c'est la publication
    -- d'origine, les suivantes sont des reprises. offre_id départage à date
    -- égale, pour que le résultat ne dépende pas de l'ordre de lecture.
    row_number() over (
        partition by signature_annonce
        order by date_creation, offre_id
    ) = 1 as est_annonce_canonique

from signatures
