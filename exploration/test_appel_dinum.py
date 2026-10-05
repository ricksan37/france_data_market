"""
DINUM enrichment: Phase 3 exploration.

Measures the matching rate of DIRECT_EMPLOYER offers against the Recherche
d'entreprises API (DINUM).

Architecture decision: the geographic filter uses the INSEE code
(lieuTravail.commune) and not the postal code, contrary to what §7.5
indicated. Justification measured on the 213 target offers:
  - postal_code filled         : 166 / 213
  - INSEE code filled          : 198 / 213  (strict superset of the postal code)
  - neither                    :  15 / 213
The INSEE code thus brings +32 offers of coverage, and a 1:1 relationship with
the commune (§4.1) where a postal code can cover several communes.
"""

import duckdb
import requests
import time

URL_DINUM = "https://recherche-entreprises.api.gouv.fr/search"


def matcher_entreprise(nom_offre, code_commune_offre, resultats):
    """
    Tries to identify a single company among the DINUM API results.

    Strategy (validated by hand on Grant Thornton, Virbac, SM Haute Saône):
    1. Filter the candidates whose head office is in the right commune AND
       active.
    2. Among them, keep only those whose name matches EXACTLY.
    3. Decide according to the number of survivors.

    Returns (status, result) where status is:
    - "pas_de_resultat": no active candidate in the commune
    - "ambigu"         : candidates present, but the name does not discriminate
    - "match"          : a single candidate with the exact name -> result = its dict
    """
    nom_nettoye = nom_offre.strip().upper()

    candidats = [
        r for r in resultats
        if r.get('siege', {}).get('commune') == code_commune_offre
        and r.get('siege', {}).get('etat_administratif') == 'A'
    ]

    if len(candidats) == 0:
        return ("pas_de_resultat", None)

    candidats_nom_exact = [
        r for r in candidats
        if r.get('nom_complet', '').strip().upper() == nom_nettoye
    ]

    if len(candidats_nom_exact) == 1:
        return ("match", candidats_nom_exact[0])
    else:
        return ("ambigu", None)


# --- Step 1: target population from DuckDB ---
# Note: run from france_data_market/ (relative path ../data/)

con = duckdb.connect('../data/warehouse.duckdb', read_only=True)

offres = con.execute("""
    select employer_name, commune_code
    from fct_job_offer
    where employer_category = 'DIRECT_EMPLOYER'
""").fetchall()

con.close()

print(f"Population cible : {len(offres)} offres")


# --- Step 2: enrichment loop, rate limit 7 req/s ---

compteurs = {
    "match": 0,
    "ambigu": 0,
    "pas_de_resultat": 0,
    "sans_cle_geo": 0,
    "erreur_technique": 0,
}

for i, (nom, code_commune) in enumerate(offres, start=1):

    # Without a geographic key, the filter cannot apply: we do not guess,
    # we count them separately (15 cases expected).
    if code_commune is None or code_commune == '':
        compteurs["sans_cle_geo"] += 1
        print(f"[{i}/{len(offres)}] {nom} -> sans_cle_geo")
        continue

    params = {"q": nom, "code_commune": code_commune}

    try:
        response = requests.get(URL_DINUM, params=params)
        response.raise_for_status()
        data = response.json()
        statut, resultat = matcher_entreprise(nom, code_commune, data.get('results', []))
    except requests.exceptions.HTTPError as e:
        statut = "erreur_technique"
        print(f"  -> erreur HTTP pour '{nom}' : {e}")

    compteurs[statut] += 1
    print(f"[{i}/{len(offres)}] {nom} -> {statut}")

    time.sleep(1 / 7)


# --- Step 3: quality metric ---

print("\n--- Résultat du matching ---")
for statut, count in compteurs.items():
    pourcentage = 100 * count / len(offres)
    print(f"{statut} : {count} ({pourcentage:.1f}%)")