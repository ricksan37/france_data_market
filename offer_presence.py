"""
offer_presence.py

Presence history of offers, at the (offer, week) grain.

WHY THIS SCRIPT DOESN'T READ fct_job_offer. The `raw` source unions every
dump present on disk and deduplicates: an offer seen once stays in it
forever. Measured 2026-08-31: fct_job_offer counts 960 offers, 463 of which
had already disappeared from France Travail. A flow -- appearances,
disappearances -- therefore can't be derived from it. This script reads the
most recent RAW DUMP, i.e. exactly what the API returned that day.

TIME KEY: the Monday of the DUMP's week, read from its filename, not the run
date. The script becomes idempotent (rerunning it on the same dump adds
nothing) and the history can be rebuilt from any dump kept on disk -- that's
what lets it restart from the two existing dumps rather than starting from
scratch.

Usage: from the repo ROOT
    python3 offer_presence.py                 -> most recent dump
    python3 offer_presence.py data/raw/job_offers_2026-07-17_1403.json
"""

import csv
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

DUMPS_DIR = Path("data/raw")
PRESENCE_PATH = Path("data/snapshots/offer_presence.csv")
COLUMNS = ["week_start_date", "job_offer_id"]

DATE_PATTERN = re.compile(r"job_offers_(\d{4})-(\d{2})-(\d{2})_\d{4}\.json$")


def week_of_dump(path: Path) -> str:
    """Monday of the dump's ISO week, read from its filename.

    The filename carries the ingestion date: the date the API responded, so
    the only date that honestly qualifies an offer's presence. The script's
    run date would diverge from it as soon as an old dump is replayed.
    """
    match = DATE_PATTERN.search(path.name)
    if not match:
        raise ValueError(f"Unexpected dump filename: {path.name}")
    day = date(*(int(g) for g in match.groups()))
    return (day - timedelta(days=day.weekday())).isoformat()


def ids_from_dump(path: Path) -> set[str]:
    """Distinct job offer ids from a raw France Travail dump.

    The dump contains structural duplicates (the API's unstable index,
    observed from the first pull on: 1094 rows for 552 offers). The set
    absorbs them, like the qualify row_number() of stg_raw__ft_job_offers on
    the dbt side.
    """
    with open(path, encoding="utf-8") as fh:
        content = json.load(fh)
    offers = content["resultats"] if isinstance(content, dict) else content
    return {o["id"] for o in offers}


def write_presence(week: str, ids: set[str]) -> tuple[int, int]:
    """Adds the missing (week, job_offer_id) pairs, rewriting the file.

    The pair is the key: replaying an already-processed dump adds nothing.
    Same discipline as weekly_snapshot.py's upsert -- pure append-only writing
    had produced three rows for the single week of 2026-08-09.
    """
    PRESENCE_PATH.parent.mkdir(parents=True, exist_ok=True)

    pairs: set[tuple[str, str]] = set()
    if PRESENCE_PATH.exists():
        with open(PRESENCE_PATH, newline="", encoding="utf-8") as fh:
            pairs = {(r["week_start_date"], r["job_offer_id"]) for r in csv.DictReader(fh)}

    before = len(pairs)
    pairs |= {(week, job_offer_id) for job_offer_id in ids}

    with open(PRESENCE_PATH, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(COLUMNS)
        writer.writerows(sorted(pairs))

    return before, len(pairs)


def main() -> None:
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        dumps = sorted(DUMPS_DIR.glob("job_offers_*.json"))
        if not dumps:
            print("No job_offers_*.json dump in data/raw/.")
            return
        path = dumps[-1]  # timestamped names: the last one is the most recent

    week = week_of_dump(path)
    ids = ids_from_dump(path)
    before, after = write_presence(week, ids)

    print(f"Dump     : {path.name}")
    print(f"Week     : {week}")
    print(f"Offers   : {len(ids)} distinct")
    print(f"Presence : {before} -> {after} pairs (+{after - before})")


if __name__ == "__main__":
    main()
