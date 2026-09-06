# full_pull.py
"""
Full pull of the data scope.

Hybrid strategy chosen after exploring the ROME reference table:
- full codeROME for occupations dedicated to data (M1405, M1811, validated
  by direct inspection of the returned titles, see exploration/)
- targeted motsCles for titles scattered across catch-all ROME occupations
  (M1403, M1805, M1806, M1868 mix data with dozens of unrelated occupations)

Known and accepted limit: offers surfaced via motsCles carry no trace, in
the raw JSON, of the keyword that matched them (unlike codeROME offers,
where romeCode is already a native field of the offer). Offers aren't
modified to add this info after the fact: that would violate the "raw is
never modified" principle. Only the count per category is kept, in the
metadata.
"""

import json
from datetime import datetime
from pathlib import Path

from auth import get_access_token
from search import get_all_offers

# Collection scope: one row = one category to query.
# Tuple (readable name, API parameter type, parameter value).
CATEGORIES = [
    ("Data scientist (M1405)", "codeROME", "M1405"),
    ("Data engineer (M1811)", "codeROME", "M1811"),
    ("Data analyst", "motsCles", "data analyst"),
    ("Data architect", "motsCles", "data architect"),
    ("Decisional", "motsCles", "décisionnel"),
    ("Business Intelligence", "motsCles", "business intelligence"),
]

OUTPUT_DIR = Path("data/raw")  # "raw" layer: raw drop, never transformed here


def full_pull() -> None:
    """
    Queries every category in scope, aggregates the raw offers and writes a
    single timestamped JSON file to data/raw/.

    The file produced has two keys:
    - "metadata"  : extraction date + per-category stats (volumes, duplicates)
    - "resultats" : the concatenated list of every raw offer

    No transformation is applied to the offers (no filtering, no
    deduplication): that's the downstream dbt layer's job. Here we only
    measure and drop the file.
    """
    token, _ = get_access_token()  # a single token reused for the 6 requests

    all_offers = []
    category_stats = []

    for name, param_type, value in CATEGORIES:
        print(f"\n--- {name} ({param_type}={value}) ---")
        # The token is passed explicitly to avoid re-authenticating per category.
        offers = get_all_offers({param_type: value}, token=token)

        # "Internal" duplicates = same id returned twice WITHIN a category
        # (an effect of paginating over a live index). Measured, not fixed.
        ids = [o["id"] for o in offers]
        internal_duplicate_count = len(ids) - len(set(ids))

        category_stats.append({
            "name": name,
            "parameter_type": param_type,
            "value": value,
            "total_fetched": len(offers),
            "internal_duplicates": internal_duplicate_count,
        })

        all_offers.extend(offers)

    # Global count of unique ids (informational): cross-category duplicates
    # are expected, since the same offer can match several keywords/ROME codes.
    global_ids = [o["id"] for o in all_offers]

    metadata = {
        "extraction_date": datetime.now().isoformat(),
        "categories": category_stats,
        "total_raw_offers": len(all_offers),
        "total_unique_offer_ids": len(set(global_ids)),
    }

    dump = {"metadata": metadata, "resultats": all_offers}

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Timestamp in the filename: every pull is kept, nothing overwrites.
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    path = OUTPUT_DIR / f"job_offers_{timestamp}.json"

    # ensure_ascii=False to keep accents readable in the raw JSON.
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dump, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(all_offers)} raw offers saved to {path}")
    print(f"   ({metadata['total_unique_offer_ids']} unique IDs; "
          f"the rest will be deduplicated in dbt)")


if __name__ == "__main__":
    full_pull()
