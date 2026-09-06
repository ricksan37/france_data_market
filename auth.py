# auth.py
"""
Authentification OAuth2 à l'API France Travail (flux client_credentials).

L'API Offres d'emploi v2 exige un jeton Bearer sur chaque appel. Ce module
isole l'obtention du jeton pour que le reste du code (search, pull) n'ait
jamais à manipuler client_id / client_secret directement.

Les identifiants sont lus depuis un fichier .env (jamais commité, cf.
.gitignore) via python-dotenv ; aucun secret n'est écrit en dur dans le code.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()  # charge FT_CLIENT_ID / FT_CLIENT_SECRET depuis le .env local

# Endpoint OAuth2 de l'espace partenaire. Le realm est passé en query string
# et fait partie intégrante de l'URL attendue par France Travail.
TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire"


def get_access_token() -> tuple[str, int]:
    """
    Obtient un jeton d'accès via le flux OAuth2 client_credentials.

    Retourne un tuple (access_token, expires_in) :
    - access_token : str, à placer dans le header Authorization: Bearer ...
    - expires_in   : int, durée de validité en secondes (permet à l'appelant
                     de décider s'il doit ré-authentifier avant un pull long).

    Lève requests.HTTPError si l'authentification échoue (identifiants
    invalides, scope refusé, etc.) via raise_for_status().
    """
    client_id = os.getenv("FT_CLIENT_ID")
    client_secret = os.getenv("FT_CLIENT_SECRET")

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        # Scopes requis : accès à l'API v2 + au détail des offres (o2dsoffre).
        "scope": "api_offresdemploiv2 o2dsoffre",
    }

    response = requests.post(TOKEN_URL, data=payload)
    response.raise_for_status()  # stoppe net si l'auth échoue (fail fast)

    token_data = response.json()
    return token_data["access_token"], token_data["expires_in"]


if __name__ == "__main__":
    # Test manuel : vérifie que les identifiants du .env sont valides.
    token, expires_in = get_access_token()
    print(f"Token obtenu : {token[:20]}...")  # tronqué : on ne logue jamais le jeton entier
    print(f"Valide {expires_in} secondes")
