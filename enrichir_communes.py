"""
enrichir_communes.py

Objectif : résoudre les codes postaux présents dans fct_offre en noms de
commune lisibles, via l'API publique geo.api.gouv.fr. Scope dynamique (lit
fct_offre à chaque run, pas une liste figée) et incrémental (ne re-questionne
jamais l'API sur un code déjà résolu) — le seed reste correct au fil des pulls
hebdomadaires sans intervention manuelle sur le script.

Prérequis : dbt build préalable (lit fct_offre, même contrainte que
enrichissement_dinum.py).
Lancement : depuis la racine -> python3 enrichir_communes.py
Produit / met à jour : observatoire/seeds/mapping_communes.csv
"""

import csv
import time
from pathlib import Path

import duckdb
import requests

CHEMIN_DB = "data/warehouse.duckdb"
CHEMIN_SEED = Path("observatoire/seeds/mapping_communes.csv")
API_URL = "https://geo.api.gouv.fr/communes"


def codes_dans_fct_offre() -> set[str]:
    """Tous les code_postal actuellement présents dans fct_offre."""
    con = duckdb.connect(CHEMIN_DB, read_only=True)
    codes = con.execute("""
        select distinct code_postal
        from fct_offre
        where code_postal is not null
    """).df()["code_postal"].tolist()
    con.close()
    return set(codes)


def codes_deja_resolus() -> set[str]:
    """Codes déjà présents dans le seed (résolus ou confirmés sans
    correspondance) -- on ne les re-questionne jamais."""
    if not CHEMIN_SEED.exists():
        return set()
    with open(CHEMIN_SEED, encoding="utf-8") as f:
        return {ligne["code_postal"] for ligne in csv.DictReader(f)}


def resoudre_code(code_postal: str) -> str:
    """Interroge l'API. Renvoie le nom de la première commune trouvée, ou
    la chaîne 'NON_RESOLU' si aucune correspondance (ex. le 99999 sentinelle
    de France Travail pour lieu non renseigné) -- jamais None, pour que le
    code reste marqué comme traité et ne soit pas re-questionné au prochain run."""
    reponse = requests.get(
        API_URL,
        params={"codePostal": code_postal, "fields": "nom", "format": "json"},
        timeout=10,
    )
    reponse.raise_for_status()
    resultats = reponse.json()
    return resultats[0]["nom"] if resultats else "NON_RESOLU"


def main() -> None:
    a_resoudre = codes_dans_fct_offre() - codes_deja_resolus()

    if not a_resoudre:
        print("Aucun nouveau code postal à résoudre -- seed déjà à jour.")
        return

    print(f"{len(a_resoudre)} nouveau(x) code(s) à résoudre (sur {len(codes_dans_fct_offre())} présents dans fct_offre).")

    fichier_existe = CHEMIN_SEED.exists()
    with open(CHEMIN_SEED, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["code_postal", "nom_commune"])
        if not fichier_existe:
            writer.writeheader()

        for i, code in enumerate(sorted(a_resoudre), start=1):
            nom = resoudre_code(code)
            writer.writerow({"code_postal": code, "nom_commune": nom})
            print(f"[{i}/{len(a_resoudre)}] {code} -> {nom}")
            time.sleep(0.15)  # courtoisie envers l'API publique

    print("\nSeed mis à jour.")


if __name__ == "__main__":
    main()