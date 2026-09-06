"""
Enrichissement DINUM : exploration Phase 3.

Mesure le taux de matching des offres EMPLOYEUR_DIRECT contre l'API
Recherche d'entreprises (DINUM), conformément à la spec FR-014 / FR-015.

Décision d'architecture : le filtre géographique utilise le
code INSEE (lieuTravail.commune) et non le code postal, contrairement à
ce qu'indiquait §7.5. Justification mesurée sur les 213 offres cibles :
  - code_postal renseigné      : 166 / 213
  - code INSEE renseigné       : 198 / 213  (sur-ensemble strict du CP)
  - ni l'un ni l'autre         :  15 / 213
Le code INSEE offre donc +32 offres de couverture, et une relation 1:1
avec la commune (§4.1) là où un code postal peut couvrir plusieurs communes.
"""

import duckdb
import requests
import time

URL_DINUM = "https://recherche-entreprises.api.gouv.fr/search"


def matcher_entreprise(nom_offre, code_commune_offre, resultats):
    """
    Tente d'identifier une entreprise unique parmi les résultats de l'API DINUM.

    Stratégie (validée à la main sur Grant Thornton, Virbac, SM Haute Saône) :
    1. Filtrer les candidats dont le siège est dans la bonne commune ET actif.
    2. Parmi eux, ne garder que ceux dont le nom correspond EXACTEMENT.
    3. Décider selon le nombre de survivants.

    Retourne (statut, résultat) où statut vaut :
    - "pas_de_resultat" : aucun candidat actif dans la commune
    - "ambigu"          : candidats présents, mais le nom ne discrimine pas
    - "match"           : un seul candidat au nom exact -> résultat = son dict
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


# --- Étape 1 : population cible depuis DuckDB ---
# Note : à lancer depuis observatoire/ (chemin relatif ../data/)

con = duckdb.connect('../data/warehouse.duckdb', read_only=True)

offres = con.execute("""
    select entreprise_nom, commune
    from fct_offre
    where categorie_employeur = 'EMPLOYEUR_DIRECT'
""").fetchall()

con.close()

print(f"Population cible : {len(offres)} offres")


# --- Étape 2 : boucle d'enrichissement, rate limit 7 req/s ---

compteurs = {
    "match": 0,
    "ambigu": 0,
    "pas_de_resultat": 0,
    "sans_cle_geo": 0,
    "erreur_technique": 0,
}

for i, (nom, code_commune) in enumerate(offres, start=1):

    # Sans clé géographique, le filtre ne peut pas s'appliquer :
    # on ne devine pas, on comptabilise à part (15 cas attendus).
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


# --- Étape 3 : métrique de qualité (spec FR-015) ---

print("\n--- Résultat du matching ---")
for statut, count in compteurs.items():
    pourcentage = 100 * count / len(offres)
    print(f"{statut} : {count} ({pourcentage:.1f}%)")