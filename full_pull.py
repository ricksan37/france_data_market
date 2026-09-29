# full_pull.py
"""
Full pull of the data scope.

The scope is a list of ROME codes (CATEGORIES). ROME codes are declared by
recruiters, so none is 100 % clean (the BI codes also catch business
developers): collection aims at recall here, and each offer is qualified
as data or not downstream in dbt, which handles precision.

An offer carries a single romeCode, so categories never overlap and every
offer records natively the code that brought it in.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from auth import get_access_token
from search import get_all_offers

# Collection scope: one row = one ROME code to query.
# Tuple (readable name, API parameter type, parameter value). The parameter
# type stays explicit so a keyword search (motsCles) remains possible.
# Left out on purpose: M1889 (AI / ML engineer, outside the data market as
# defined here), M1894 (database administration, mostly IT ops and data
# entry), M1414 (statistician, few offers, half of them lab technicians).
CATEGORIES = [
    ("Data scientist (M1405)", "codeROME", "M1405"),
    ("Data engineer (M1811)", "codeROME", "M1811"),
    ("Data analyst (M1419)", "codeROME", "M1419"),
    ("Data architect / database architect (M1868)", "codeROME", "M1868"),
    ("BI analyst (M1851)", "codeROME", "M1851"),
    ("BI developer (M1824)", "codeROME", "M1824"),
    ("BI consultant (M1872)", "codeROME", "M1872"),
    ("Chief Data Officer (M1423)", "codeROME", "M1423"),
]

OUTPUT_DIR = Path("data/raw")  # "raw" layer: raw drop, never transformed here

# Dropped at ingestion, never written to disk. They carry recruiter names,
# emails and phone numbers (254 of the 1,094 offers in the July dump), and
# France Travail's reuse licence explicitly excludes contact data from
# republication. The pipeline never reads them, and a dump can end up
# versioned in a public repo (the July reference dump is), so the only safe
# place to remove them is here, before the file exists.
PERSONAL_DATA_FIELDS = ("contact", "agence")

# Completeness guard: the Content-Range total is the reference for what
# exists. Without it, a pagination that keeps serving the same page would
# look like a small market. Tolerance: the index is live, so the total
# drifts during a pull; a few offers of slack absorb that drift, while a
# capped page (150 fetched out of several hundred) stays far beyond it.
COMPLETENESS_MIN_SLACK = 5          # offers
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
        # Warning only, never a failure: 0 offers is a legitimate API answer
        # (204 + "*/0"), but a category dropping to 0 more likely means the
        # API or the keyword stopped matching than that the market vanished.
        if total == 0:
            print(f"  ⚠ {stat['value']}: 0 offers announced, check the search criteria")
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
        # With a correct pagination the expected value is 0: a non-zero count
        # points to a page served twice. Kept in the metadata as a check.
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

    # Global count of unique ids (informational). An offer has a single
    # romeCode, so this should equal len(all_offers); a gap would mean the
    # live index moved an offer between codes during the pull.
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
    # argparse rather than `"--dry-run" in sys.argv`: an unknown or mistyped
    # argument (--dryrun) must stop the script, not be silently ignored while
    # a real dump gets written and picked up by dbt.
    # allow_abbrev=False: "--dry" must not be accepted as "--dry-run".
    parser = argparse.ArgumentParser(description="Full pull of the data scope.", allow_abbrev=False)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="collect and run the completeness check, but write no dump",
    )
    args = parser.parse_args()
    full_pull(dry_run=args.dry_run)
