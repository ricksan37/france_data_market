"""
offer_presence.py

Presence history of offers, at the (week, offer) grain: which offers each
weekly pull returned. fct_weekly_market_flow derives appearances and exits
from it. The file is committed every week and is the only trace of past
pulls (runner dumps are not kept): it can't be rebuilt, so a wrong write
stays.

WHY IT READS THE RAW DUMP, NOT fct_job_offer. The weekly workflow runs it
right after the pull and before dbt build, and its time key comes from the
dump's filename, which the warehouse doesn't carry.

TIME KEY: the Monday of the DUMP's week, read from its filename, not the run
date: replaying an old dump files it under its own week.

ONE PULL PER WEEK: writing a dump REPLACES its week's offers. A rerun
within the same week (after a failure, or a manual trigger) makes the
latest pull win, the same rule as weekly_snapshot.py's upsert. Adding to
the week instead would merge two pulls into a set of offers the API never
returned. Replaying the same dump changes nothing. A local run records a
local pull: run weekly_snapshot.py on the same dump too (after dbt build)
and commit both files together, so both histories describe the same pull.

Usage: from the repo ROOT
    python3 offer_presence.py                 -> most recent dump
    python3 offer_presence.py data/raw/job_offers_2026-07-17_1403.json
"""

import argparse
import csv
import json
import re
from datetime import date, timedelta
from pathlib import Path

DUMPS_DIR = Path("data/raw")
PRESENCE_PATH = Path("data/snapshots/offer_presence.csv")
COLUMNS = ["week_start_date", "job_offer_id"]

DATE_PATTERN = re.compile(r"job_offers_(\d{4})-(\d{2})-(\d{2})_\d{4}\.json$")


def week_of_dump(path: Path) -> str:
    """Monday of the dump's ISO week, read from its filename.

    The filename carries the ingestion date: the date the API responded, so
    the only date that honestly qualifies an offer's presence.

    Returns:
        The Monday as an ISO date string (YYYY-MM-DD).

    Raises:
        ValueError: the filename doesn't match job_offers_YYYY-MM-DD_HHMM.json.
    """
    match = DATE_PATTERN.search(path.name)
    if not match:
        raise ValueError(f"Unexpected dump filename: {path.name}")
    day = date(*(int(g) for g in match.groups()))
    return (day - timedelta(days=day.weekday())).isoformat()


def ids_from_dump(path: Path) -> set[str]:
    """Distinct job offer ids of a raw France Travail dump.

    A set: an offer returned twice in one pull counts once, like the
    deduplication of stg_raw__ft_job_offers on the dbt side.

    Returns:
        The set of job offer ids, possibly empty.

    Raises:
        OSError, json.JSONDecodeError, KeyError: unreadable file, invalid
            JSON, or a dump without the resultats key.
    """
    with open(path, encoding="utf-8") as fh:
        content = json.load(fh)
    return {offer["id"] for offer in content["resultats"]}


def write_presence(week: str, ids: set[str]) -> tuple[int, int, int]:
    """Replaces the week's (week, job_offer_id) pairs with the dump's,
    rewriting the file.

    Returns:
        (pairs before, pairs of that week before, pairs after).

    Raises:
        OSError: the presence file can't be read or written.
    """
    PRESENCE_PATH.parent.mkdir(parents=True, exist_ok=True)

    pairs: set[tuple[str, str]] = set()
    if PRESENCE_PATH.exists():
        with open(PRESENCE_PATH, newline="", encoding="utf-8") as fh:
            pairs = {(r["week_start_date"], r["job_offer_id"]) for r in csv.DictReader(fh)}

    before = len(pairs)
    week_before = sum(1 for pair_week, _ in pairs if pair_week == week)
    pairs = {pair for pair in pairs if pair[0] != week}
    pairs |= {(week, job_offer_id) for job_offer_id in ids}

    with open(PRESENCE_PATH, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(COLUMNS)
        writer.writerows(sorted(pairs))

    return before, week_before, len(pairs)


def main(dump_path: Path | None) -> None:
    """Writes the presence of one dump: the given one, or the most recent.

    Returns:
        None.

    Raises:
        ValueError, OSError, json.JSONDecodeError, KeyError: propagated from
            week_of_dump(), ids_from_dump() and write_presence().
    """
    if dump_path is None:
        dumps = sorted(DUMPS_DIR.glob("job_offers_*.json"))
        if not dumps:
            print("No job_offers_*.json dump in data/raw/.")
            return
        dump_path = dumps[-1]  # timestamped names: the last one is the most recent

    week = week_of_dump(dump_path)
    ids = ids_from_dump(dump_path)
    before, week_before, after = write_presence(week, ids)

    print(f"Dump     : {dump_path.name}")
    print(f"Week     : {week}")
    print(f"Offers   : {len(ids)} distinct")
    print(f"Week     : {week_before} -> {len(ids)} pairs (replaced)")
    print(f"Presence : {before} -> {after} pairs")


if __name__ == "__main__":
    # argparse rather than sys.argv: an unknown option must stop the script
    # instead of being read as a dump path.
    parser = argparse.ArgumentParser(
        description="Record which offers a pull returned, under the dump's week.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "dump",
        nargs="?",
        type=Path,
        help="dump to record (default: the most recent data/raw/job_offers_*.json)",
    )
    args = parser.parse_args()
    main(args.dump)
