# search.py
"""
Search functions for the France Travail Job Offers API v2.

The search parameter is a generic dict rather than a fixed keyword, to
support the hybrid strategy chosen for the "data" scope:
- full codeROME for dedicated occupations (e.g. M1405 Data scientist, M1811 Data engineer)
- targeted motsCles for titles scattered across catch-all occupations
  (e.g. "data analyst", "data architect", "decisional")

Two functions:
- search_offers    : a single call (useful for exploration / debugging)
- get_all_offers   : full pagination (used by the production pull)
"""

from auth import get_access_token
import requests

SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"


def search_offers(params: dict) -> dict:
    """
    A single search call (one page, max 150 results).

    params: query parameter dict, e.g. {"motsCles": "data analyst"}
            or {"codeROME": "M1405"}: passed as-is to the API.

    Returns the full response JSON (resultats, filtresPossibles...).

    The prints are intentional: this function is mainly used for interactive
    exploration, where seeing the HTTP status and Content-Range helps
    understand what the API returns.
    """
    token, _ = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(SEARCH_URL, headers=headers, params=params)

    print(f"HTTP status: {response.status_code}")

    data = response.json()
    print(f"Offers in this page: {len(data.get('resultats', []))}")

    # Content-Range carries the total available (e.g. "offres 0-149/1234"),
    # key info to know whether to paginate, used by get_all_offers.
    content_range = response.headers.get("Content-Range")
    print(f"Content-Range: {content_range}")

    return data


def get_all_offers(params: dict, token: str | None = None) -> list[dict]:
    """
    Fetches ALL offers for a given search, paginating past the 150-result
    per-call limit.

    params: query parameter dict (motsCles, codeROME, etc.). The Range
            header is handled internally, no need to pass it.
    token: an already-obtained token (avoids re-authenticating per category
           during a multi-category pull). If None, requests a new one.

    Absolute API ceiling: 1150 results (range 0-1149). Beyond that, the
    search would need to be narrowed down (e.g. by date), out of scope for
    now.

    Returns the list of offers. Possible duplicates included (live search
    index, see the earlier observation): deduplication is
    stg_raw__ft_job_offers's job on the dbt side, not this function's.
    """
    if token is None:
        token, _ = get_access_token()

    all_results = []
    start = 0
    page_size = 150
    max_start = 1149  # absolute API ceiling
    total = None      # actual total, discovered on the 1st call via Content-Range

    while start <= max_start:
        # Current page window, bounded by the API ceiling...
        end = min(start + page_size - 1, max_start)
        # ...then by the actual total once known (avoids a final call that
        # would go past the number of existing offers).
        if total is not None:
            end = min(end, total - 1)

        headers = {
            "Authorization": f"Bearer {token}",
            "Range": f"offres={start}-{end}",  # pagination via the Range header
        }

        response = requests.get(SEARCH_URL, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        all_results.extend(data.get("resultats", []))

        # Read the total after each call: "offres 0-149/1234" -> 1234.
        content_range = response.headers.get("Content-Range")
        if content_range:
            total = int(content_range.split("/")[-1])

        # Last page reached: everything has been fetched, exit.
        if total is not None and end >= total - 1:
            break

        start += page_size

    # Quality measurement: actual volume per occupation. Informational only:
    # nothing is filtered here, dedup happens downstream via dbt.
    ids = [offer["id"] for offer in all_results]
    duplicate_count = len(ids) - len(set(ids))
    if duplicate_count > 0:
        print(f"⚠ {duplicate_count} duplicate(s) detected out of {len(ids)} offers "
              f"(pagination on a live index, expected; dedup downstream via dbt)")

    return all_results


if __name__ == "__main__":
    # Example of the two filtering modes chosen for the data scope
    ds_offers = get_all_offers({"codeROME": "M1405"})
    print(f"\nTotal M1405 (Data scientist): {len(ds_offers)}")

    da_offers = get_all_offers({"motsCles": "data analyst"})
    print(f"Total 'data analyst' (motsCles): {len(da_offers)}")
