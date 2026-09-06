import duckdb
import requests
import time

URL_DINUM = "https://recherche-entreprises.api.gouv.fr/search"

import re

MOTS_VIDES = {"DE", "LA", "LE", "DU", "DES", "ET", "D", "L"}

def normaliser_nom(nom):
    """
    Nettoyage renforcé pour comparaison souple :
    - majuscule, espaces superflus retirés
    - ponctuation (apostrophes, tirets, points) remplacée par un espace
    - mots vides français retirés (articles/prépositions qui varient
      selon que l'offre cite le nom complet ou une forme raccourcie)
    """
    nom = nom.strip().upper()
    nom = re.sub(r"[.,'\-]", " ", nom)
    mots = [m for m in nom.split() if m not in MOTS_VIDES]
    return " ".join(mots)

def diagnostiquer(nom_offre, code_commune_offre, resultats, total_results_api):

    candidats = [
        r for r in resultats
        if r.get('siege', {}).get('commune') == code_commune_offre
        and r.get('siege', {}).get('etat_administratif') == 'A'
    ]

    if len(candidats) == 0:
        return "pas_de_resultat", None

    candidats_nom_exact = [
        r for r in candidats
        if normaliser_nom(r.get('nom_complet', '')) == normaliser_nom(nom_offre)
    ]

    if len(candidats_nom_exact) == 1:
        return "match", candidats_nom_exact[0].get('nom_complet')

    if len(candidats_nom_exact) == 0:
        return "ambigu_zero_exact", f"total_results={total_results_api}, candidats page 1={[c.get('nom_complet') for c in candidats][:3]}"
    else:
        return "ambigu_multiple_exact", [c.get('nom_complet') for c in candidats_nom_exact]

con = duckdb.connect('../data/warehouse.duckdb', read_only=True)
offres = con.execute("""
    select entreprise_nom, commune
    from fct_offre
    where categorie_employeur = 'EMPLOYEUR_DIRECT'
""").fetchall()
con.close()

compteurs = {}
exemples = {}

for i, (nom, code_commune) in enumerate(offres, start=1):
    if code_commune is None or code_commune == '':
        statut, detail = "sans_cle_geo", None
    elif nom.strip().upper() == "EY":
        # Déjà diagnostiqué : sigle sans correspondance légale.
        # On ne refait pas l'appel API, la conclusion est connue.
        statut, detail = "pas_de_resultat_sigle_connu", None
    else:
        params = {"q": nom, "code_commune": code_commune}
        try:
            response = requests.get(URL_DINUM, params=params)
            response.raise_for_status()
            data = response.json()
            total_api = data.get('total_results')
            statut, detail = diagnostiquer(nom, code_commune, data.get('results', []), total_api)
            detail = f"total_results API (national, avant filtre commune) = {total_api}"
        except requests.exceptions.HTTPError as e:
            statut, detail = "erreur_technique", str(e)
        time.sleep(1 / 7)

    compteurs[statut] = compteurs.get(statut, 0) + 1
    exemples.setdefault(statut, [])
    if len(exemples[statut]) < 6:
        exemples[statut].append((nom, detail))

    print(f"[{i}/{len(offres)}] {nom} -> {statut}")

print("\n--- Résultat détaillé ---")
for statut, count in sorted(compteurs.items(), key=lambda x: -x[1]):
    pct = 100 * count / len(offres)
    print(f"{statut} : {count} ({pct:.1f}%)")

print("\n--- Exemples par catégorie ---")
for statut, exs in exemples.items():
    print(f"\n{statut} :")
    for nom, detail in exs:
        print(f"  {nom} -> {detail}")