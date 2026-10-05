# check_codeROME.py
"""
Exploration script: inspect the job titles of a given ROME code.

Goal of this step (Phase 1): decide, ROME code by ROME code, whether the job
is "pure data" (it can be taken whole through codeROME) or "catch-all" (it
should be targeted through motsCles instead). So we look at the first 15
titles returned to get a feel for what the code really contains.

Conclusion drawn from these trials: M1405 and M1811 are dedicated to data;
M1403, M1805, M1806 and M1868 mix data with many other jobs. This observation
underpins the final hybrid strategy (see search.py / full_pull.py).

Throwaway script, kept in exploration/ to trace the approach.
"""

from auth import get_access_token
import requests

SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"


def search_by_rome(code_rome: str) -> None:
    """
    Prints the first 15 job titles for a ROME code.

    code_rome: str, e.g. "M1868". Queries the API without pagination (a single
    call is enough to judge the content of the code). Returns nothing: the
    goal is reading on screen, not reusing the data.
    """
    token, _ = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {"codeROME": code_rome}

    response = requests.get(SEARCH_URL, headers=headers, params=params)
    print(f"Statut HTTP : {response.status_code}")

    # Exploration guard: on error, print the raw body (the API's error
    # message) and stop there.
    if response.status_code != 200:
        print(response.text)
        return

    data = response.json()
    resultats = data.get("resultats", [])
    print(f"Offres trouvées : {len(resultats)}\n")

    # 15 titles are enough to judge whether the code is "data" or catch-all.
    for o in resultats[:15]:
        print(f"  {o.get('intitule')}")


if __name__ == "__main__":
    search_by_rome("M1868")  # code tested: "catch-all" case ruled out of the scope
