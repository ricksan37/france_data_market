# search.py
"""
Fonctions de recherche sur l'API Offres d'emploi v2 France Travail.

Le paramètre de recherche est un dict générique plutôt qu'un mot-clé fixe,
pour supporter la stratégie hybride retenue pour le périmètre "data" :
- codeROME entier pour les métiers dédiés (ex: M1405 Data scientist, M1811 Data engineer)
- motsCles ciblé pour les intitulés isolés dans des métiers fourre-tout
  (ex: "data analyst", "data architect", "décisionnel")

Deux fonctions :
- search_offres     : un seul appel (utile pour l'exploration / le debug)
- get_all_offres    : pagination complète (utilisé par le pull de production)
"""

from auth import get_access_token
import requests

SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"


def search_offres(params: dict) -> dict:
    """
    Un seul appel de recherche (page unique, max 150 résultats).

    params : dict de paramètres de requête, ex. {"motsCles": "data analyst"}
             ou {"codeROME": "M1405"} : passé tel quel à l'API.

    Retourne le JSON complet de la réponse (resultats, filtresPossibles...).

    Les print sont volontaires : cette fonction sert surtout à l'exploration
    interactive, où voir le statut HTTP et le Content-Range aide à comprendre
    ce que renvoie l'API.
    """
    token, _ = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(SEARCH_URL, headers=headers, params=params)

    print(f"Statut HTTP : {response.status_code}")

    data = response.json()
    print(f"Offres dans cette page : {len(data.get('resultats', []))}")

    # Content-Range renseigne le total disponible (ex: "offres 0-149/1234"),
    # info clé pour savoir s'il faut paginer, exploitée par get_all_offres.
    content_range = response.headers.get("Content-Range")
    print(f"Content-Range : {content_range}")

    return data


def get_all_offres(params: dict, token: str | None = None) -> list[dict]:
    """
    Récupère TOUTES les offres pour une recherche donnée, en paginant
    au-delà de la limite de 150 résultats par appel (spec §3.3).

    params : dict de paramètres de requête (motsCles, codeROME, etc.).
             Le header Range est géré en interne, pas besoin de le passer.
    token : jeton déjà obtenu (évite une ré-authentification par catégorie
            lors d'un pull multi-catégories). Si None, en demande un neuf.

    Plafond absolu de l'API : 1150 résultats (range 0-1149). Au-delà,
    il faudrait affiner la recherche (ex: par date), hors scope pour l'instant.

    Retourne la liste des offres. Doublons possibles inclus (index de
    recherche live, cf. observation précédente) : le dédoublonnage est
    le rôle de stg_ft_offres en dbt, pas de cette fonction (spec §7.2).
    """
    if token is None:
        token, _ = get_access_token()

    all_resultats = []
    start = 0
    page_size = 150
    max_start = 1149  # plafond absolu de l'API, spec §3.3
    total = None      # total réel, découvert au 1er appel via Content-Range

    while start <= max_start:
        # Fenêtre de la page courante, bornée par le plafond API...
        end = min(start + page_size - 1, max_start)
        # ...puis par le total réel dès qu'on le connaît (évite un dernier
        # appel qui dépasserait le nombre d'offres existantes).
        if total is not None:
            end = min(end, total - 1)

        headers = {
            "Authorization": f"Bearer {token}",
            "Range": f"offres={start}-{end}",  # pagination par header Range
        }

        response = requests.get(SEARCH_URL, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        all_resultats.extend(data.get("resultats", []))

        # On lit le total après chaque appel : "offres 0-149/1234" -> 1234.
        content_range = response.headers.get("Content-Range")
        if content_range:
            total = int(content_range.split("/")[-1])

        # Dernière page atteinte : on a tout récupéré, on sort.
        if total is not None and end >= total - 1:
            break

        start += page_size

    # Mesure de qualité (spec Phase 1 : "Mesurer : volume réel par métier").
    # Informatif seulement : on ne filtre rien ici, dédup en aval via dbt.
    ids = [offre["id"] for offre in all_resultats]
    n_doublons = len(ids) - len(set(ids))
    if n_doublons > 0:
        print(f"⚠ {n_doublons} doublon(s) détecté(s) sur {len(ids)} offres "
              f"(pagination sur index temps réel, attendu ; dédup en aval via dbt)")

    return all_resultats


if __name__ == "__main__":
    # Exemple des deux modes de filtrage retenus pour le périmètre data
    offres_ds = get_all_offres({"codeROME": "M1405"})
    print(f"\nTotal M1405 (Data scientist) : {len(offres_ds)}")

    offres_da = get_all_offres({"motsCles": "data analyst"})
    print(f"Total 'data analyst' (motsCles) : {len(offres_da)}")
