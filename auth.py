# auth.py
"""
OAuth2 authentication for the France Travail API (client_credentials flow).

The Job Offers API v2 requires a Bearer token on every call. This module
isolates token retrieval so that the rest of the code (search, pull) never
has to handle client_id / client_secret directly.

Credentials are read from environment variables. Locally, python-dotenv
loads them from the .env file (never committed, see .gitignore). In CI,
GitHub Actions injects them from the repository secrets; load_dotenv() then
finds no .env file and overrides nothing. No secret is hardcoded.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()  # loads FT_CLIENT_ID / FT_CLIENT_SECRET from the local .env

# OAuth2 endpoint of the partner space. The realm is passed as a query string
# and is part of the URL expected by France Travail.
TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire"
# Without a timeout, requests waits forever if the server never answers.
REQUEST_TIMEOUT_SECONDS = 30


def get_access_token() -> tuple[str, int]:
    """
    Obtains an access token via the OAuth2 client_credentials flow.

    Returns a tuple (access_token, expires_in):
    - access_token: str, to be placed in the header Authorization: Bearer ...
    - expires_in:   int, validity period in seconds (1499 s measured,
                    about 25 minutes).

    Known limitation: no caller renews the token. A full pull makes about
    12 calls (8 ROME codes, 1 to 3 pages each; 64 in the worst case), well
    within the token lifetime.

    Raises:
    - KeyError if FT_CLIENT_ID or FT_CLIENT_SECRET is missing from the
      environment (fails here with the variable name, rather than with a
      misleading HTTP error further down);
    - requests.HTTPError if the server refuses authentication, with the
      server's error message included;
    - requests.Timeout if the server does not respond within
      REQUEST_TIMEOUT_SECONDS.
    """
    client_id = os.environ["FT_CLIENT_ID"]
    client_secret = os.environ["FT_CLIENT_SECRET"]

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        # Both scopes are required, including for search: a token without
        # o2dsoffre gets a 403 insufficient_scope on /offres/search
        # (measured 2026-09-28).
        "scope": "api_offresdemploiv2 o2dsoffre",
    }

    response = requests.post(TOKEN_URL, data=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    # Not raise_for_status(): it drops the server's error message, the only clue to diagnose.
    if not response.ok:
        raise requests.HTTPError(
            f"Authentication refused ({response.status_code}): {response.text}", response=response
        )

    token_data = response.json()
    return token_data["access_token"], token_data["expires_in"]


if __name__ == "__main__":
    # Manual test: checks that the credentials in .env are valid.
    token, expires_in = get_access_token()
    print(f"Token obtained: {token[:20]}...")  # truncated: never log the full token
    print(f"Valid for {expires_in} seconds")
