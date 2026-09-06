-- zone_geographique ne prend que trois valeurs. Test singulier plutôt que
-- accepted_values : le test générique compile un IN() à plusieurs valeurs, que
-- le bug d'optimiseur DuckDB fait planter dans une vue interrogée.
-- Convention du projet depuis, pour tout contrôle sur un ensemble de valeurs.
--
-- 'inconnue' est une valeur à part entière, pas un trou : 101 offres sur 960
-- n'ont ni code postal ni code INSEE. Les compter comme métropole par défaut
-- gonflerait la métropole de 10 % du corpus sur une supposition.

select offre_id, zone_geographique
from {{ ref('fct_offre') }}
where zone_geographique != 'metropole'
  and zone_geographique != 'outre-mer'
  and zone_geographique != 'inconnue'
