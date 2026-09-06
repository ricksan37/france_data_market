"""
Inventaire du dump d'enrichissement DINUM avant déclaration en source dbt.

Pourquoi ce script : read_json_auto infère un schéma unique pour tout le
tableau `resultats`. Or ce tableau est hétérogène : 171 lignes portent un
résultat d'entreprise, 42 n'en portent aucun. Si les clés entreprise sont
ABSENTES (et non présentes à null) sur les lignes non matchées, l'inférence
peut produire un STRUCT incomplet et perdre des champs silencieusement.
On mesure donc, par clé, la présence ET le remplissage avant d'écrire
la moindre ligne de SQL.

Lancement : depuis france_data_market/  ->  python3 ../exploration/inspect_dump_dinum.py
"""

import glob
import json
from collections import Counter, defaultdict

MOTIF_DUMP = "../data/raw/enrich_dinum_*.json"


def charger_dump_le_plus_recent(motif: str) -> tuple[str, dict]:
    """Retourne (chemin, contenu) du dump le plus récent.

    Le tri lexicographique suffit : l'horodatage AAAA-MM-JJ_HHMM est
    naturellement ordonnable. Tous les fichiers trouvés sont affichés,
    car la décision « source sur fichier fixe ou sur glob » dépend
    directement de leur nombre.
    """
    fichiers = sorted(glob.glob(motif))
    if not fichiers:
        raise FileNotFoundError(f"Aucun fichier ne correspond a {motif}")

    print(f"Fichiers correspondant au motif ({len(fichiers)}) :")
    for f in fichiers:
        print(f"   - {f}")

    chemin = fichiers[-1]
    print(f"\nDump retenu : {chemin}\n")

    with open(chemin, encoding="utf-8") as fh:
        return chemin, json.load(fh)


def inventorier_cles(resultats: list[dict]) -> None:
    """Affiche, pour chaque clé rencontrée : présence, remplissage, types.

    La distinction présence / remplissage est le coeur du diagnostic :
    - presente == len(resultats)  -> clé toujours là, DuckDB la verra
    - presente < len(resultats)   -> clé absente sur certaines lignes,
                                     risque d'inférence incomplète
    """
    presence = Counter()
    remplissage = Counter()
    types_vus = defaultdict(set)

    for r in resultats:
        for cle, valeur in r.items():
            presence[cle] += 1
            if valeur is not None:
                remplissage[cle] += 1
                types_vus[cle].add(type(valeur).__name__)

    total = len(resultats)
    print(f"{'CLE':<38} {'PRESENTE':>9} {'NON NULLE':>10}  TYPES")
    print("-" * 80)
    for cle in presence:
        drapeau = "" if presence[cle] == total else "   <-- absente sur certaines lignes"
        types = ",".join(sorted(types_vus[cle])) or "toujours null"
        print(f"{cle:<38} {presence[cle]:>9} {remplissage[cle]:>10}  {types}{drapeau}")

    # Sous-structures : si une valeur est un dict, ses sous-clés comptent aussi.
    for cle in presence:
        sous_cles = set()
        for r in resultats:
            valeur = r.get(cle)
            if isinstance(valeur, dict):
                sous_cles.update(valeur.keys())
        if sous_cles:
            print(f"\n   Sous-cles de '{cle}' : {sorted(sous_cles)}")


def trouver_cle_siren(resultats: list[dict]) -> str | None:
    """Localise la clé portant le SIREN sans présumer de son nom exact."""
    for r in resultats:
        for cle in r:
            if cle.lower() == "siren" or cle.lower().endswith("_siren"):
                return cle
    return None


def main() -> None:
    _, dump = charger_dump_le_plus_recent(MOTIF_DUMP)

    print("=" * 80)
    print("1. STRUCTURE DE PREMIER NIVEAU")
    print("=" * 80)
    print(f"Cles racine : {list(dump.keys())}\n")
    print("Bloc metadata :")
    print(json.dumps(dump.get("metadata", {}), indent=2, ensure_ascii=False))

    resultats = dump["resultats"]

    print("\n" + "=" * 80)
    print("2. VOLUMES")
    print("=" * 80)
    print(f"len(resultats) = {len(resultats)}   (attendu : 213)")

    cle_siren = trouver_cle_siren(resultats)
    if cle_siren:
        avec_siren = sum(1 for r in resultats if r.get(cle_siren))
        print(f"SIREN non nul  = {avec_siren}   (attendu : 171)  [cle : '{cle_siren}']")
    else:
        print("Aucune cle 'siren' trouvee au premier niveau des resultats.")

    # Répartition des statuts : confirme la volumétrie par voie de matching.
    cle_statut = next(
        (c for r in resultats for c in r if "statut" in c.lower()), None
    )
    if cle_statut:
        print(f"\nRepartition de '{cle_statut}' :")
        for statut, n in Counter(r.get(cle_statut) for r in resultats).most_common():
            print(f"   {str(statut):<40} {n:>4}")

    print("\n" + "=" * 80)
    print("3. INVENTAIRE DES CLES")
    print("=" * 80)
    inventorier_cles(resultats)

    print("\n" + "=" * 80)
    print("4. EXEMPLES BRUTS")
    print("=" * 80)

    exemple_matche = next((r for r in resultats if cle_siren and r.get(cle_siren)), None)
    exemple_non_matche = next(
        (r for r in resultats if not cle_siren or not r.get(cle_siren)), None
    )

    print("--- Resultat MATCHE ---")
    print(json.dumps(exemple_matche, indent=2, ensure_ascii=False))
    print("\n--- Resultat NON MATCHE ---")
    print(json.dumps(exemple_non_matche, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()