"""
presence_offres.py

Historique de presence des offres, au grain (offre, semaine) -- Phase 5.

POURQUOI CE SCRIPT NE LIT PAS fct_offre. La source `raw` unionne tous les
dumps presents sur disque et dedoublonne : une offre vue une fois y reste pour
toujours. Mesure du 31/08 : fct_offre compte 960 offres dont 463 avaient deja
disparu de France Travail. Un flux -- apparitions, disparitions -- ne peut donc
pas s'en deduire. Ce script lit le DUMP BRUT le plus recent, c'est-a-dire
exactement ce que l'API a renvoye ce jour-la.

CLE TEMPORELLE : le lundi de la semaine du DUMP, lu dans son nom de fichier,
et non la date d'execution. Le script devient idempotent (le relancer sur le
meme dump n'ajoute rien) et l'historique est reamorcable depuis n'importe quel
dump conserve -- c'est ce qui permet de repartir des deux dumps existants
plutot que de commencer a zero.

Lancement : depuis la RACINE du repo
    python3 presence_offres.py                 -> dump le plus recent
    python3 presence_offres.py data/raw/offres_2026-07-17_1403.json
"""

import csv
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

DOSSIER_DUMPS = Path("data/raw")
CHEMIN_PRESENCE = Path("data/snapshots/presence_offres.csv")
COLONNES = ["semaine", "offre_id"]

MOTIF_DATE = re.compile(r"offres_(\d{4})-(\d{2})-(\d{2})_\d{4}\.json$")


def semaine_du_dump(chemin: Path) -> str:
    """Lundi de la semaine ISO du dump, lu dans son nom de fichier.

    Le nom porte la date de l'ingestion : c'est la date a laquelle l'API a
    repondu, donc la seule date qui qualifie honnetement la presence d'une
    offre. La date d'execution du script en differerait des qu'on rejoue un
    dump ancien.
    """
    trouve = MOTIF_DATE.search(chemin.name)
    if not trouve:
        raise ValueError(f"Nom de dump inattendu : {chemin.name}")
    jour = date(*(int(g) for g in trouve.groups()))
    return (jour - timedelta(days=jour.weekday())).isoformat()


def ids_du_dump(chemin: Path) -> set[str]:
    """offre_id distincts d'un dump brut France Travail.

    Le dump contient des doublons structurels (index instable de l'API,
    constate des la Session 1 : 1094 lignes pour 552 offres). Le set les
    absorbe, comme le qualify row_number() de stg_ft_offres cote dbt.
    """
    with open(chemin, encoding="utf-8") as fh:
        contenu = json.load(fh)
    offres = contenu["resultats"] if isinstance(contenu, dict) else contenu
    return {o["id"] for o in offres}


def ecrire_presence(semaine: str, ids: set[str]) -> tuple[int, int]:
    """Ajoute les couples (semaine, offre_id) absents, en reecrivant le fichier.

    Le couple est la cle : rejouer un dump deja traite n'ajoute rien. C'est la
    meme discipline que l'upsert de snapshot_hebdo.py -- l'ecriture en append
    pur avait produit trois lignes pour la seule semaine du 09/08.
    """
    CHEMIN_PRESENCE.parent.mkdir(parents=True, exist_ok=True)

    couples: set[tuple[str, str]] = set()
    if CHEMIN_PRESENCE.exists():
        with open(CHEMIN_PRESENCE, newline="", encoding="utf-8") as fh:
            couples = {(l["semaine"], l["offre_id"]) for l in csv.DictReader(fh)}

    avant = len(couples)
    couples |= {(semaine, offre_id) for offre_id in ids}

    with open(CHEMIN_PRESENCE, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(COLONNES)
        writer.writerows(sorted(couples))

    return avant, len(couples)


def main() -> None:
    if len(sys.argv) > 1:
        chemin = Path(sys.argv[1])
    else:
        dumps = sorted(DOSSIER_DUMPS.glob("offres_*.json"))
        if not dumps:
            print("Aucun dump offres_*.json dans data/raw/.")
            return
        chemin = dumps[-1]  # noms horodates : le dernier est le plus recent

    semaine = semaine_du_dump(chemin)
    ids = ids_du_dump(chemin)
    avant, apres = ecrire_presence(semaine, ids)

    print(f"Dump      : {chemin.name}")
    print(f"Semaine   : {semaine}")
    print(f"Offres    : {len(ids)} distinctes")
    print(f"Presence  : {avant} -> {apres} couples (+{apres - avant})")


if __name__ == "__main__":
    main()
