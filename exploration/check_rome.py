# check_rome.py
"""
Exploration script: which ROME codes hide behind a keyword?

The mirror of check_codeROME.py. Here we start from a keyword (e.g. "data
architect") and count the distribution of ROME codes among the matching
offers. It answers the question: "does this keyword fall into a single clean
ROME code, or is it scattered over many codes?".

This count is what showed that some data job titles have no dedicated ROME
code and are scattered across catch-all jobs, hence the use of motsCles
filtering for these cases (hybrid strategy, see full_pull.py).

Throwaway script, kept in exploration/ to trace the approach.
"""

from search import search_offers
from collections import Counter


def check_rome(mots_cles: str) -> None:
    """
    Prints the distribution of (ROME code, label) for the offers matching a
    keyword.

    mots_cles: str passed to the API as the motsCles parameter. A single call
    (search_offers, unpaginated): the sample from the first page is enough to
    see the dispersion. Sorted from most to least frequent.
    """
    # search_offers expects a dict of API parameters: we wrap the keyword.
    data = search_offers({"motsCles": mots_cles})
    resultats = data.get("resultats", [])

    # Counts (code, label) pairs: one entry = one distinct ROME code.
    counts = Counter(
        (o.get("romeCode"), o.get("romeLibelle")) for o in resultats
    )

    # Right-align the count (>3) so the columns read cleanly.
    for (code, libelle), n in counts.most_common():
        print(f"{n:>3}  {code}  {libelle}")


if __name__ == "__main__":
    check_rome("data architect")  # case tested: keyword scattered over several ROME codes
