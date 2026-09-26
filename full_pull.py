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
import sys
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

# Dropped at ingestion, never written to disk. They carry recruiter names,
# emails and phone numbers (254 of the 1,094 offers in the July dump), and
# France Travail's reuse licence explicitly excludes contact data from
# republication. The pipeline never reads them, and a dump can end up
# versioned in a public repo (the July reference dump is), so the only safe
# place to remove them is here, before the file exists.
PERSONAL_DATA_FIELDS = ("contact", "agence")

# Completeness guard. Until 2026-09-26 the pagination sent its range in a
# header the API ignores: every page returned the same first 150 offers, and
# M1811 / "data analyst" were silently capped at 150 unique offers for two
# months (427 and 221 existed). Nothing failed, because nothing compared what
# was fetched with what the API said exists. The Content-Range total is that
# reference. Tolerance: the index is live, so the total drifts during a pull
# (the July M1811 pull came back with 151 uniques, one more than the page).
# A few offers of slack absorbs that drift; a capped page (150 vs 427) is
# nowhere near it.
COMPLETENESS_MIN_SLACK = 5         # offers
COMPLETENESS_RELATIVE_SLACK = 0.02  # share of the announced total
# Pagination limit of the API (range 0-1149). Past it, offers are unreachable
# whatever the code does: the search must be narrowed, so fail rather than
# collect a truncated category.
API_PAGINATION_LIMIT = 1150


def check_completeness(category_stats: list[dict]) -> None:
    """
    Fails the pull if a category fetched noticeably fewer unique offers than
    the API announces, or more than the API can serve. Runs before the dump
    is written: a truncated dump never reaches data/raw/, so it can't be
    rebuilt into the marts or into the presence history.

    Prints every category (not only the failing ones) so a failure shows the
    full picture in the CI log.
    """
    failures = []
    print("\n--- Completeness check (unique fetched vs Content-Range total) ---")
    for stat in category_stats:
        total = stat["api_total"]
        unique = stat["unique_fetched"]
        if total is None:
            verdict = "FAIL: no Content-Range, completeness cannot be checked"
        elif total > API_PAGINATION_LIMIT:
            verdict = (f"FAIL: {total} results exceed the API pagination "
                       f"limit ({API_PAGINATION_LIMIT}), narrow the search")
        else:
            slack = max(COMPLETENESS_MIN_SLACK, COMPLETENESS_RELATIVE_SLACK * total)
            if unique < total - slack:
                verdict = (f"FAIL: {total - unique} missing "
                           f"(tolerance {slack:.0f})")
            else:
                verdict = "ok"
        print(f"  {stat['value']:<24} api_total={str(total):>5}  "
              f"unique_fetched={unique:>5}  {verdict}")
        if verdict != "ok":
            failures.append(f"{stat['value']}: {verdict}")

    if failures:
        raise RuntimeError(
            "Incomplete pull, no dump written:\n  " + "\n  ".join(failures)
        )


def full_pull(dry_run: bool = False) -> None:
    """
    Queries every category in scope, aggregates the raw offers and writes a
    single timestamped JSON file to data/raw/.

    The file produced has two keys:
    - "metadata"  : extraction date + per-category stats (volumes, duplicates)
    - "resultats" : the concatenated list of every raw offer

    No transformation is applied to the offers (no filtering, no
    deduplication): that's the downstream dbt layer's job. Here we only
    measure and drop the file. One exception: the "contact" and "agence"
    fields are dropped before writing (see PERSONAL_DATA_FIELDS).

    dry_run: collect and run the completeness check, but write nothing.
    Checks the pagination against the live API without adding a dump that
    dbt would pick up through the job_offers_*.json glob.
    """
    token, _ = get_access_token()  # a single token reused for the 6 requests

    all_offers = []
    category_stats = []

    for name, param_type, value in CATEGORIES:
        print(f"\n--- {name} ({param_type}={value}) ---")
        # The token is passed explicitly to avoid re-authenticating per category.
        offers, api_total = get_all_offers({param_type: value}, token=token)

        # "Internal" duplicates = same id returned twice WITHIN a category.
        # Before 2026-09-26 they came from a pagination the API ignored
        # (same page served repeatedly), not from a live index. Correctly
        # paginated, the expected value is 0; kept in the metadata as a check.
        ids = [o["id"] for o in offers]
        internal_duplicate_count = len(ids) - len(set(ids))

        category_stats.append({
            "name": name,
            "parameter_type": param_type,
            "value": value,
            "total_fetched": len(offers),
            "internal_duplicates": internal_duplicate_count,
            "unique_fetched": len(set(ids)),
            "api_total": api_total,
        })

        for offer in offers:
            for field in PERSONAL_DATA_FIELDS:
                offer.pop(field, None)
        all_offers.extend(offers)

    # Global count of unique ids (informational): cross-category duplicates
    # are expected, since the same offer can match several keywords/ROME codes.
    global_ids = [o["id"] for o in all_offers]

    check_completeness(category_stats)
    if dry_run:
        print(f"\nDry run: {len(set(global_ids))} unique offers, no dump written.")
        return

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
    full_pull(dry_run="--dry-run" in sys.argv)
