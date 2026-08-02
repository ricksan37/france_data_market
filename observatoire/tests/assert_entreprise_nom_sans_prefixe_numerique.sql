{{ config(
    severity = 'warn',
    tags = ['known_issue']
) }}

-- Détecte les noms d'entreprise (issus de l'offre brute, avant matching DINUM)
-- portant un préfixe numérique parasite : un identifiant interne du recruteur
-- (code de service, référence RH) collé devant le vrai nom, séparé par un tiret.
-- Exemples mesurés en S5 : "751163-DIR STRATEGIE INNOVATION ET TRANSFO",
-- "929840-PARIS DIRECTION...". Ce n'est pas un nom d'entreprise exploitable tel quel.
--
-- SEVERITY: WARN, décision assumée (S5, 01/08/2026) — 2 occurrences sur 213,
-- pas assez pour construire une règle de nettoyage défendable (principe projet :
-- jamais de correction sur un cas isolé, et 2 cas ne garantissent pas encore que
-- le motif "chiffres + tiret" est stable, sans faux positif type "3M" ou "42Data").
-- Le WARN garde le pipeline vert tout en surveillant une dérive : si ce nombre
-- augmente avec de nouvelles données, ça devient un signal pour construire un
-- vrai nettoyage (regexp_replace en staging) plutôt qu'une simple alerte.
--
-- Contrat dbt : 0 ligne = pass, >= 1 ligne = warn (pas fail).

select
    offre_id,
    entreprise_nom_offre
from {{ ref('stg_dinum_entreprises') }}
where regexp_matches(entreprise_nom_offre, '^[0-9]+-')