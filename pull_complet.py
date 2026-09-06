# pull_complet.py
"""
Pull complet du périmètre data (Phase 1, point 4 de la spec).

Stratégie hybride retenue après exploration du référentiel ROME :
- codeROME entier pour les métiers dédiés à la data (M1405, M1811, validés
  par inspection directe des intitulés retournés, cf. exploration/)
- motsCles ciblé pour les intitulés isolés dans des métiers ROME fourre-tout
  (M1403, M1805, M1806, M1868 mélangent data et dizaines de métiers sans rapport)

Limite connue et acceptée : les offres remontées par motsCles ne portent pas,
dans le JSON brut, de trace du mot-clé qui les a fait matcher (contrairement
aux offres codeROME, où romeCode est déjà un champ natif de l'offre). On ne
modifie pas les offres pour ajouter cette info a posteriori : ça violerait
le principe "raw jamais modifié" (spec §7.2). Seul le compte par catégorie
est conservé, dans le metadata.
"""

import json
from datetime import datetime
from pathlib import Path

from auth import get_access_token
from search import get_all_offres

# Périmètre de collecte : une ligne = une catégorie à interroger.
# Tuple (nom lisible, type de paramètre API, valeur du paramètre).
CATEGORIES = [
    ("Data scientist (M1405)", "codeROME", "M1405"),
    ("Data engineer (M1811)", "codeROME", "M1811"),
    ("Data analyst", "motsCles", "data analyst"),
    ("Data architect", "motsCles", "data architect"),
    ("Décisionnel", "motsCles", "décisionnel"),
    ("Business Intelligence", "motsCles", "business intelligence"),
]

OUTPUT_DIR = Path("data/raw")  # couche "raw" : dépôt brut, jamais transformé ici


def pull_complet() -> None:
    """
    Interroge chaque catégorie du périmètre, agrège les offres brutes et
    écrit un unique fichier JSON horodaté dans data/raw/.

    Le fichier produit contient deux clés :
    - "metadata"  : date d'extraction + stats par catégorie (volumes, doublons)
    - "resultats" : la liste concaténée de toutes les offres brutes

    Aucune transformation n'est appliquée aux offres (pas de filtrage, pas de
    dédoublonnage) : c'est le rôle de la couche dbt en aval (spec §7.2). Ici
    on ne fait que mesurer et déposer.
    """
    token, _ = get_access_token()  # un seul token réutilisé pour les 6 requêtes

    toutes_les_offres = []
    stats_categories = []

    for nom, type_param, valeur in CATEGORIES:
        print(f"\n--- {nom} ({type_param}={valeur}) ---")
        # Le token est passé explicitement pour éviter une ré-auth par catégorie.
        offres = get_all_offres({type_param: valeur}, token=token)

        # Doublons "internes" = même id renvoyé deux fois DANS une catégorie
        # (effet de la pagination sur un index temps réel). Mesuré, pas corrigé.
        ids = [o["id"] for o in offres]
        n_doublons_internes = len(ids) - len(set(ids))

        stats_categories.append({
            "nom": nom,
            "type_parametre": type_param,
            "valeur": valeur,
            "total_recupere": len(offres),
            "doublons_internes": n_doublons_internes,
        })

        toutes_les_offres.extend(offres)

    # Comptage global des id uniques (indicatif) : les doublons inter-catégories
    # sont attendus, une même offre pouvant matcher plusieurs mots-clés / ROME.
    ids_globaux = [o["id"] for o in toutes_les_offres]

    metadata = {
        "date_extraction": datetime.now().isoformat(),
        "categories": stats_categories,
        "total_offres_brutes": len(toutes_les_offres),
        "total_offres_id_uniques": len(set(ids_globaux)),
    }

    dump = {"metadata": metadata, "resultats": toutes_les_offres}

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Horodatage dans le nom de fichier : chaque pull est conservé, rien n'écrase.
    horodatage = datetime.now().strftime("%Y-%m-%d_%H%M")
    chemin = OUTPUT_DIR / f"offres_{horodatage}.json"

    # ensure_ascii=False pour garder les accents lisibles dans le JSON brut.
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(dump, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(toutes_les_offres)} offres brutes sauvegardées dans {chemin}")
    print(f"   ({metadata['total_offres_id_uniques']} ID uniques ; "
          f"le reste sera dédoublonné en dbt)")


if __name__ == "__main__":
    pull_complet()
