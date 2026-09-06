# check_codeROME.py
"""
Script d'exploration : inspecter les intitulés d'offres d'un code ROME donné.

Objectif de l'étape (Phase 1) : décider, code ROME par code ROME, si le métier
est "pur data" (on peut le prendre en entier via codeROME) ou "fourre-tout"
(il faudra plutôt cibler par motsCles). On regarde donc les 15 premiers
intitulés renvoyés pour se faire une idée du contenu réel du code.

Conclusion tirée de ces essais : M1405 et M1811 sont dédiés data ; M1403,
M1805, M1806, M1868 mélangent data et beaucoup d'autres métiers. Cette
observation fonde la stratégie hybride finale (cf. search.py / full_pull.py).

Script jetable, gardé dans exploration/ pour tracer la démarche.
"""

from auth import get_access_token
import requests

SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"


def search_by_rome(code_rome: str) -> None:
    """
    Affiche les 15 premiers intitulés d'offres pour un code ROME.

    code_rome : str, ex. "M1868". Interroge l'API sans pagination (un seul
    appel suffit pour juger du contenu du code). Ne retourne rien : le but
    est la lecture à l'écran, pas la réutilisation des données.
    """
    token, _ = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {"codeROME": code_rome}

    response = requests.get(SEARCH_URL, headers=headers, params=params)
    print(f"Statut HTTP : {response.status_code}")

    # Garde-fou d'exploration : en cas d'erreur, on affiche le corps brut
    # (message d'erreur de l'API) et on s'arrête là.
    if response.status_code != 200:
        print(response.text)
        return

    data = response.json()
    resultats = data.get("resultats", [])
    print(f"Offres trouvées : {len(resultats)}\n")

    # 15 intitulés suffisent pour juger si le code est "data" ou fourre-tout.
    for o in resultats[:15]:
        print(f"  {o.get('intitule')}")


if __name__ == "__main__":
    search_by_rome("M1868")  # code testé : cas "fourre-tout" écarté du périmètre
