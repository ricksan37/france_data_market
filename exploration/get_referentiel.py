# get_referentiel.py
"""
Exploration script: fetch a reference list from the API and pre-filter the
data-related appellations.

The API exposes reference lists (communes, appellations, etc.). Here we fetch
the "appellations" list (the official list of job titles) and sift it on a few
data keywords to spot, upstream, all the labels likely to interest us. It
serves to frame the scope before querying the offers.

Throwaway script, kept in exploration/ to trace the approach.
"""

from auth import get_access_token
import requests

# URL parameterized by reference type ({type} formatted at call time).
REFERENTIEL_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/referentiel/{type}"


def get_referentiel(type_referentiel: str) -> list[dict] | None:
    """
    Fetches a complete reference list from the API.

    type_referentiel: str, e.g. "appellations". Returns the decoded JSON
    (list of dicts) on success, or None if the call fails, in which case the
    response body is printed for diagnosis.
    """
    token, _ = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = REFERENTIEL_URL.format(type=type_referentiel)

    response = requests.get(url, headers=headers)
    print(f"Statut HTTP : {response.status_code}")

    if response.status_code != 200:
        print(response.text)  # useful to see the exact error message
        return None

    return response.json()


if __name__ == "__main__":
    appellations = get_referentiel("appellations")

    if appellations:
        print(f"Total appellations dans le référentiel : {len(appellations)}")

        # Pre-filter: keep only the labels containing one of these words.
        mots_cles = ["data", "analytic", "décisionnel", "business intelligence"]
        matches = [
            a for a in appellations
            if any(mot in a["libelle"].lower() for mot in mots_cles)
        ]
        matches.sort(key=lambda a: a["libelle"])  # alphabetical sort for readability

        print(f"\n{len(matches)} appellations pré-filtrées :\n")
        for a in matches:
            print(f"  {a['code']:>10}  {a['libelle']}")
