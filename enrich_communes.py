"""
enrich_communes.py

Goal: resolve the postal codes present in fct_job_offer into readable
commune names, via the public geo.api.gouv.fr API. Dynamic scope (reads
fct_job_offer on every run, not a frozen list) and incremental (never
re-queries the API on an already resolved code): the seed stays correct
across weekly pulls without manual intervention on the script.

Prerequisite: a prior dbt build (reads fct_job_offer, same constraint as
enrich_dinum.py).
Usage: from the root -> python3 enrich_communes.py
Produces / updates: france_data_market/seeds/mapping_communes.csv
"""

import csv
import time
from pathlib import Path

import duckdb
import requests

DB_PATH = "data/warehouse.duckdb"
SEED_PATH = Path("france_data_market/seeds/mapping_communes.csv")
API_URL = "https://geo.api.gouv.fr/communes"


def codes_in_fct_job_offer() -> list[tuple[str, str]]:
    """All geographic keys from fct_job_offer, with their kind.

    Two kinds, because the source provides two. Paris, Lyon and Marseille
    are the three French communes with arrondissements: they have no single
    postal code, so France Travail returns their overall commune's INSEE
    code (75056, 69123, 13055) with an empty postal code. Measured
    2026-09-04: 95 offers in this case, 77 of them in Paris, more than half
    of the corpus's Parisian offers, invisible in the geographic dimension
    as long as it was indexed on postal code alone.

    The two kinds are indistinguishable by eye (75056 and 75001 are both
    five-digit numbers), hence the flag: it's the value's origin that
    decides the API parameter, never its shape.
    """
    con = duckdb.connect(DB_PATH, read_only=True)
    rows = con.execute("""
        select distinct
            coalesce(postal_code, commune_code) as key,
            case when postal_code is not null then 'postal' else 'insee' end as kind
        from fct_job_offer
        where coalesce(postal_code, commune_code) is not null
    """).fetchall()
    con.close()
    return rows


def already_resolved_codes() -> set[str]:
    """Codes already present in the seed (resolved or confirmed with no
    match) -- never re-queried."""
    if not SEED_PATH.exists():
        return set()
    with open(SEED_PATH, encoding="utf-8") as f:
        return {row["commune_key"] for row in csv.DictReader(f)}


def resolve_code(key: str, kind: str) -> str:
    """Queries the API according to the key's kind.

    Returns the name of the first commune found, or the string 'UNRESOLVED'
    if there's no match (e.g. France Travail's 99999 sentinel for an
    unspecified location) -- never None, so the key stays marked as
    processed and isn't re-queried on the next run.

    The parameter changes with the kind: codePostal for a postal code, code
    for an INSEE code. Querying one with the other's parameter raises no
    error, it simply returns an empty list -- the failure would therefore be
    silent and read as an unresolved code.
    """
    parameter = "codePostal" if kind == "postal" else "code"
    response = requests.get(
        API_URL,
        params={parameter: key, "fields": "nom", "format": "json"},
        timeout=10,
    )
    response.raise_for_status()
    results = response.json()
    return results[0]["nom"] if results else "UNRESOLVED"


def main() -> None:
    all_codes = codes_in_fct_job_offer()
    already_resolved = already_resolved_codes()
    to_resolve = [(key, kind) for key, kind in all_codes if key not in already_resolved]

    if not to_resolve:
        print("No new key to resolve -- seed already up to date.")
        return

    print(f"{len(to_resolve)} new key(s) to resolve (out of {len(all_codes)} present in fct_job_offer).")

    file_exists = SEED_PATH.exists()
    with open(SEED_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["commune_key", "commune_name"])
        if not file_exists:
            writer.writeheader()

        for i, (key, kind) in enumerate(sorted(to_resolve), start=1):
            name = resolve_code(key, kind)
            writer.writerow({"commune_key": key, "commune_name": name})
            print(f"[{i}/{len(to_resolve)}] {key} ({kind}) -> {name}")
            time.sleep(0.15)  # courtesy toward the public API

    print("\nSeed updated.")


if __name__ == "__main__":
    main()
