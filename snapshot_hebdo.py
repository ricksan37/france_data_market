"""
snapshot_hebdo.py

Objectif : calculer un instantané hebdomadaire du marché (Phase 5, spec §13.1)
et l'ajouter à data/snapshots/marche_hebdo.csv, seul artefact persisté entre
deux runs CI (le warehouse.duckdb et les dumps JSON restent éphémères/gitignorés).

En mode CI_SANS_EXTRACTION (workflow GitHub Actions), fct_offre_technologie
est vide -- top_technologie vaut alors "non disponible (CI)" plutôt que
de planter sur un fetchone() vide.

Lancement : depuis la racine du repo -> python3 snapshot_hebdo.py
"""

import csv
from datetime import date
from pathlib import Path

import duckdb

CHEMIN_DB = "data/warehouse.duckdb"
CHEMIN_SNAPSHOT = Path("data/snapshots/marche_hebdo.csv")

COLONNES = [
    "semaine",
    "nb_offres_total",
    "nb_anonyme",
    "nb_intermediaire",
    "nb_intermediaire_reclasse",
    "nb_employeur_direct",
    "salaire_median_annuel",
    "top_technologie",
]


def calculer_snapshot(con: duckdb.DuckDBPyConnection) -> dict:
    """Calcule les métriques du jour sur l'état actuel de fct_offre."""

    nb_total = con.execute("select count(*) from fct_offre").fetchone()[0]

    nb_par_categorie = dict(con.execute("""
        select categorie_employeur, count(*)
        from fct_offre
        group by categorie_employeur
    """).fetchall())

    salaire_median = con.execute("""
        select median(salaire_min)
        from fct_offre
        where salaire_periode = 'annuel'
    """).fetchone()[0]

    resultat_top_technologie = con.execute("""
        select technologie
        from fct_offre_technologie
        group by technologie
        order by count(*) desc
        limit 1
    """).fetchone()
    # None si fct_offre_technologie est vide (mode CI_SANS_EXTRACTION, Session 7) :
    # fetchone() renvoie None lui-même, pas (None,), quand 0 ligne ne matche.
    top_technologie = resultat_top_technologie[0] if resultat_top_technologie else "non disponible (CI)"

    return {
        "semaine": date.today().isoformat(),
        "nb_offres_total": nb_total,
        "nb_anonyme": nb_par_categorie.get("ANONYME", 0),
        "nb_intermediaire": nb_par_categorie.get("INTERMEDIAIRE", 0),
        "nb_intermediaire_reclasse": nb_par_categorie.get("INTERMEDIAIRE_reclasse", 0),
        "nb_employeur_direct": nb_par_categorie.get("EMPLOYEUR_DIRECT", 0),
        "salaire_median_annuel": salaire_median,
        "top_technologie": top_technologie,
    }


def ecrire_ligne(snapshot: dict) -> None:
    """Ajoute une ligne au CSV, en créant le header si le fichier n'existe pas."""
    CHEMIN_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    fichier_existe = CHEMIN_SNAPSHOT.exists()

    with open(CHEMIN_SNAPSHOT, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLONNES)
        if not fichier_existe:
            writer.writeheader()
        writer.writerow(snapshot)


def main() -> None:
    con = duckdb.connect(CHEMIN_DB, read_only=True)
    snapshot = calculer_snapshot(con)
    con.close()

    ecrire_ligne(snapshot)

    print("--- Snapshot ajouté ---")
    for cle, valeur in snapshot.items():
        print(f"  {cle} : {valeur}")


if __name__ == "__main__":
    main()