-- Staging de l'historique de presence (Phase 5).
-- Grain : 1 ligne = 1 couple (offre, semaine ou elle a ete vue dans un pull).
-- Aucune logique metier ici (regle §7.2) : typage explicite, rien d'autre.
--
-- offre_id reste en varchar : les identifiants France Travail comportent des
-- zeros de tete (0020136) qu'un cast numerique detruirait silencieusement.

select
    semaine::date as semaine,
    offre_id::varchar as offre_id
from {{ source('presence', 'presence_offres') }}
