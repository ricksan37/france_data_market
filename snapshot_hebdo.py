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
from datetime import date, timedelta
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
    "extraction_llm",
]


def lundi_de_la_semaine() -> str:
    """Cle du snapshot : le lundi de la semaine ISO, pas la date d'execution.

    date.today() faisait de la date du run la cle : trois declenchements
    manuels le 09/08 ont produit trois lignes distinctes pour une meme
    semaine, grain que fct_marche_hebdo aurait herite casse. Le lundi reste
    un axe de dates directement exploitable en graphique, contrairement a
    une notation "2026-W32".
    """
    aujourdhui = date.today()
    return (aujourdhui - timedelta(days=aujourdhui.weekday())).isoformat()


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
        "semaine": lundi_de_la_semaine(),
        "nb_offres_total": nb_total,
        "nb_anonyme": nb_par_categorie.get("ANONYME", 0),
        "nb_intermediaire": nb_par_categorie.get("INTERMEDIAIRE", 0),
        # En CI_SANS_EXTRACTION, INTERMEDIAIRE_reclasse n'existe pas : la
        # reclassification dépend des champs d'extraction LLM, absents du runner.
        # Renvoyer 0 ferait passer une absence pour une mesure nulle -- une courbe
        # 21 -> 0 -> 0 se lit comme un effondrement. get() sans défaut renvoie None,
        # que DictWriter écrit en cellule vide : absence explicite, jamais silencieuse.
        "nb_intermediaire_reclasse": nb_par_categorie.get("INTERMEDIAIRE_reclasse"),
        "nb_employeur_direct": nb_par_categorie.get("EMPLOYEUR_DIRECT", 0),
        "salaire_median_annuel": salaire_median,
        "top_technologie": top_technologie,
        # Deduit du resultat de requete, pas d'une variable d'environnement
        # relue en aval (meme choix que top_technologie, plus robuste). Sans
        # cette colonne, une semaine sans champs LLM est indistinguable d'une
        # semaine ou le LLM n'aurait rien trouve.
        "extraction_llm": bool(resultat_top_technologie),
    }


def ecrire_ligne(snapshot: dict) -> None:
    """Upsert par semaine : une semaine = une ligne, la derniere ecriture gagne.

    L'ancien mode append laissait trois lignes pour le 09/08 (deux tests
    workflow_dispatch plus le run reel). Reecrire le fichier entier coute
    quelques kilo-octets et garantit l'unicite du grain a la source, plutot
    que de la rattraper par un qualify dans chaque modele aval.

    Une relance en cours de semaine ecrase donc la ligne de la semaine : c'est
    voulu, la mesure la plus recente est la bonne. Un run local (champs LLM
    remplis) prend ainsi le pas sur le run CI du lundi, et extraction_llm
    trace lequel des deux a produit la ligne.
    """
    CHEMIN_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)

    lignes: dict[str, dict] = {}
    if CHEMIN_SNAPSHOT.exists():
        with open(CHEMIN_SNAPSHOT, newline="", encoding="utf-8") as fh:
            for ligne in csv.DictReader(fh):
                lignes[ligne["semaine"]] = ligne
    lignes[snapshot["semaine"]] = snapshot

    with open(CHEMIN_SNAPSHOT, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLONNES)
        writer.writeheader()
        for semaine in sorted(lignes):
            writer.writerow(lignes[semaine])


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