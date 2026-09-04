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


def codes_dans_fct_offre() -> list[tuple[str, str]]:
    """Toutes les clés géographiques de fct_offre, avec leur nature.

    Deux natures, parce que la source en fournit deux. Paris, Lyon et
    Marseille sont les trois communes françaises à arrondissements : elles
    n'ont pas de code postal unique, donc France Travail renvoie leur code
    INSEE de commune globale (75056, 69123, 13055) avec un code postal vide.
    Mesuré le 04/09 : 95 offres dans ce cas, dont 77 à Paris, soit plus de la
    moitié des offres parisiennes du corpus, invisibles dans la dimension
    géographique tant qu'elle ne s'indexait que sur le code postal.

    Les deux natures sont indiscernables à l'oeil (75056 et 75001 sont deux
    nombres à cinq chiffres), d'où le drapeau : c'est l'origine de la valeur
    qui décide du paramètre d'API, jamais sa forme.
    """
    con = duckdb.connect(CHEMIN_DB, read_only=True)
    lignes = con.execute("""
        select distinct
            coalesce(code_postal, commune) as cle,
            case when code_postal is not null then 'postal' else 'insee' end as nature
        from fct_offre
        where coalesce(code_postal, commune) is not null
    """).fetchall()
    con.close()
    return lignes


def codes_deja_resolus() -> set[str]:
    """Codes déjà présents dans le seed (résolus ou confirmés sans
    correspondance) -- on ne les re-questionne jamais."""
    if not CHEMIN_SEED.exists():
        return set()
    with open(CHEMIN_SEED, encoding="utf-8") as f:
        return {ligne["cle_commune"] for ligne in csv.DictReader(f)}


def resoudre_code(cle: str, nature: str) -> str:
    """Interroge l'API selon la nature de la clé.

    Renvoie le nom de la première commune trouvée, ou la chaîne 'NON_RESOLU'
    si aucune correspondance (ex. le 99999 sentinelle de France Travail pour
    lieu non renseigné) -- jamais None, pour que la clé reste marquée comme
    traitée et ne soit pas re-questionnée au prochain run.

    Le paramètre change avec la nature : codePostal pour un code postal, code
    pour un code INSEE. Les interroger l'un pour l'autre ne lève aucune erreur,
    ça renvoie simplement une liste vide -- l'échec serait donc silencieux et
    se lirait comme un code non résolu.
    """
    parametre = "codePostal" if nature == "postal" else "code"
    reponse = requests.get(
        API_URL,
        params={parametre: cle, "fields": "nom", "format": "json"},
        timeout=10,
    )
    reponse.raise_for_status()
    resultats = reponse.json()
    return resultats[0]["nom"] if resultats else "NON_RESOLU"


def main() -> None:
    toutes = codes_dans_fct_offre()
    deja = codes_deja_resolus()
    a_resoudre = [(cle, nature) for cle, nature in toutes if cle not in deja]

    if not a_resoudre:
        print("Aucune nouvelle clé à résoudre -- seed déjà à jour.")
        return

    print(f"{len(a_resoudre)} nouvelle(s) clé(s) à résoudre (sur {len(toutes)} présentes dans fct_offre).")

    fichier_existe = CHEMIN_SEED.exists()
    with open(CHEMIN_SEED, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["cle_commune", "nom_commune"])
        if not fichier_existe:
            writer.writeheader()

        for i, (cle, nature) in enumerate(sorted(a_resoudre), start=1):
            nom = resoudre_code(cle, nature)
            writer.writerow({"cle_commune": cle, "nom_commune": nom})
            print(f"[{i}/{len(a_resoudre)}] {cle} ({nature}) -> {nom}")
            time.sleep(0.15)  # courtoisie envers l'API publique

    print("\nSeed mis à jour.")


if __name__ == "__main__":
    main()