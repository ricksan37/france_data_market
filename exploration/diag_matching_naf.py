import duckdb
import requests
import time
import re

URL_DINUM = "https://recherche-entreprises.api.gouv.fr/search"
MOTS_VIDES = {"DE", "LA", "LE", "DU", "DES", "ET", "D", "L"}


def normaliser_nom(nom):
    """Normalisation souple : casse, ponctuation, mots vides français retirés."""
    nom = nom.strip().upper()
    nom = re.sub(r"[.,'\-]", " ", nom)
    return " ".join(m for m in nom.split() if m not in MOTS_VIDES)


def diagnostiquer(nom_offre, code_commune, code_naf_offre, resultats):
    """
    Matching en cascade :
    1. commune + établissement actif
    2. nom normalisé identique
    3. si toujours ambigu ET NAF disponible -> départage par NAF
    4. si le nom ne matche jamais -> tentative de repêchage par NAF seul
    """
    candidats = [
        r for r in resultats
        if r.get('siege', {}).get('commune') == code_commune
        and r.get('siege', {}).get('etat_administratif') == 'A'
    ]

    if len(candidats) == 0:
        return "pas_de_resultat", None

    nom_cible = normaliser_nom(nom_offre)
    par_nom = [r for r in candidats if normaliser_nom(r.get('nom_complet', '')) == nom_cible]

    if len(par_nom) == 1:
        return "match_nom", par_nom[0].get('nom_complet')

    # Cas ambigu sur le nom -> on tente le départage par NAF
    if len(par_nom) > 1 and code_naf_offre:
        par_naf = [r for r in par_nom if r.get('activite_principale') == code_naf_offre]
        if len(par_naf) == 1:
            return "match_nom_puis_naf", par_naf[0].get('nom_complet')
        return "ambigu_multiple_exact", [r.get('nom_complet') for r in par_nom]

    if len(par_nom) > 1:
        return "ambigu_multiple_exact", [r.get('nom_complet') for r in par_nom]

    # Le nom ne matche aucun candidat -> repêchage par NAF seul (piste C)
    if code_naf_offre:
        par_naf = [r for r in candidats if r.get('activite_principale') == code_naf_offre]
        if len(par_naf) == 1:
            return "match_naf_sans_nom", par_naf[0].get('nom_complet')
        if len(par_naf) > 1:
            return "ambigu_zero_exact_naf_multiple", [r.get('nom_complet') for r in par_naf][:3]

    return "ambigu_zero_exact", [r.get('nom_complet') for r in candidats][:3]


con = duckdb.connect('../data/warehouse.duckdb', read_only=True)
offres = con.execute("""
    select entreprise_nom, commune, code_naf
    from fct_offre
    where categorie_employeur = 'EMPLOYEUR_DIRECT'
""").fetchall()
con.close()

compteurs = {}
exemples = {}

for i, (nom, commune, code_naf) in enumerate(offres, start=1):
    if commune is None or commune == '':
        statut, detail = "sans_cle_geo", None
    elif nom.strip().upper() == "EY":
        statut, detail = "pas_de_resultat_sigle_connu", None
    else:
        params = {"q": nom, "code_commune": commune}
        try:
            resp = requests.get(URL_DINUM, params=params)
            resp.raise_for_status()
            statut, detail = diagnostiquer(nom, commune, code_naf, resp.json().get('results', []))
        except requests.exceptions.HTTPError as e:
            statut, detail = "erreur_technique", str(e)
        time.sleep(1 / 7)

    compteurs[statut] = compteurs.get(statut, 0) + 1
    exemples.setdefault(statut, [])
    if len(exemples[statut]) < 5:
        exemples[statut].append((nom, detail))

    print(f"[{i}/{len(offres)}] {nom} -> {statut}")

print("\n--- Résultat détaillé ---")
total_match = 0
for statut, count in sorted(compteurs.items(), key=lambda x: -x[1]):
    pct = 100 * count / len(offres)
    print(f"{statut} : {count} ({pct:.1f}%)")
    if statut.startswith("match"):
        total_match += count
print(f"\nTOTAL MATCH (toutes voies) : {total_match} ({100*total_match/len(offres):.1f}%)")

print("\n--- Exemples ---")
for statut, exs in exemples.items():
    print(f"\n{statut} :")
    for nom, detail in exs:
        print(f"  {nom} -> {detail}")