"""
weekly_snapshot.py

Computes the weekly market snapshot on fct_job_offer and writes it to
data/snapshots/weekly_market.csv, one row per week, read back by
fct_weekly_market. Committed every week with offer_presence.csv: the two
files are the only history persisted between runs (runner dumps and the
warehouse are not kept), so a wrong row can't be rebuilt.

WEEK KEY: the Monday of the week of the dump the warehouse describes (the
most recent job_offers_*.json, the one stg_raw__ft_job_offers keeps), with
offer_presence.py's own function: both histories file a pull under the same
week. Not the run date: a local run on another day would otherwise file a
pull under a week it doesn't belong to.

ONE ROW PER WEEK, the latest write wins. A local run (LLM fields populated)
thus replaces the CI row of its own dump's week; llm_extraction_available
traces which kind of run produced the row. A local dump is a different pull
from the runner's: record that same dump in both histories, in this order
(offer_presence.py, dbt build, weekly_snapshot.py), and commit both files
together. Otherwise the two histories describe different pulls for the
same week.

In CI_WITHOUT_EXTRACTION mode, fct_job_offer_technology is empty:
top_technology is then "not available (CI)" and the reclassified
intermediary count is left empty, not 0.

Usage: from the repo root, after dbt build -> python3 weekly_snapshot.py
"""

import argparse
import csv
from pathlib import Path

import duckdb

from offer_presence import DUMPS_DIR, week_of_dump

DB_PATH = "data/warehouse.duckdb"
SNAPSHOT_PATH = Path("data/snapshots/weekly_market.csv")

COLUMNS = [
    "week_start_date",
    "total_offer_count",
    "anonymous_offer_count",
    "intermediary_offer_count",
    "reclassified_intermediary_offer_count",
    "direct_employer_offer_count",
    "median_annual_salary",
    "top_technology",
    "llm_extraction_available",
]


def week_of_latest_dump() -> str:
    """Monday of the week of the most recent job offers dump.

    Returns:
        The Monday as an ISO date string (YYYY-MM-DD).

    Raises:
        SystemExit: no job offers dump in data/raw/.
        ValueError: the latest dump's filename doesn't carry a date.
    """
    dumps = sorted(DUMPS_DIR.glob("job_offers_*.json"))
    if not dumps:
        raise SystemExit("No job_offers_*.json dump in data/raw/: nothing to snapshot.")
    return week_of_dump(dumps[-1])


def compute_snapshot(con: duckdb.DuckDBPyConnection, week: str) -> dict:
    """Computes the week's metrics on the current state of fct_job_offer.

    Returns:
        A dict keyed by COLUMNS.

    Raises:
        duckdb.Error: a query fails (e.g. dbt build has not run).
    """

    total_count = con.execute("select count(*) from fct_job_offer").fetchone()[0]

    count_by_category = dict(con.execute("""
        select employer_category, count(*)
        from fct_job_offer
        group by employer_category
    """).fetchall())

    # annual_salary_plausible: an implausible amount (a monthly salary typed
    # in the annual field) must not enter an annual aggregate.
    median_salary = con.execute("""
        select median(salary_min)
        from fct_job_offer
        where salary_period = 'annual'
          and annual_salary_plausible
    """).fetchone()[0]

    top_technology_result = con.execute("""
        select technology
        from fct_job_offer_technology
        group by technology
        order by count(*) desc
        limit 1
    """).fetchone()
    # None if fct_job_offer_technology is empty (CI_WITHOUT_EXTRACTION mode):
    # fetchone() itself returns None, not (None,), when 0 rows match.
    top_technology = top_technology_result[0] if top_technology_result else "not available (CI)"

    return {
        "week_start_date": week,
        "total_offer_count": total_count,
        "anonymous_offer_count": count_by_category.get("ANONYMOUS", 0),
        "intermediary_offer_count": count_by_category.get("INTERMEDIARY", 0),
        # In CI_WITHOUT_EXTRACTION, INTERMEDIARY_RECLASSIFIED doesn't exist:
        # the reclassification depends on LLM extraction fields, absent from
        # the runner. Returning 0 would pass an absence off as a zero
        # measurement -- a curve going 21 -> 0 -> 0 reads as a collapse.
        # get() with no default returns None, which DictWriter writes as an
        # empty cell: an explicit absence, never a silent one.
        "reclassified_intermediary_offer_count": count_by_category.get("INTERMEDIARY_RECLASSIFIED"),
        "direct_employer_offer_count": count_by_category.get("DIRECT_EMPLOYER", 0),
        "median_annual_salary": median_salary,
        "top_technology": top_technology,
        # Derived from the query result, not from an environment variable
        # re-read downstream. Without this column, a week with no LLM fields
        # would be indistinguishable from a week where the LLM found nothing.
        "llm_extraction_available": bool(top_technology_result),
    }


def write_row(snapshot: dict) -> None:
    """Upsert by week: one week = one row, the latest write wins.

    Rewriting the whole file costs a few kilobytes and guarantees the grain
    at the source, rather than deduplicating in every consuming model.

    Returns:
        None.

    Raises:
        OSError: the snapshot file can't be read or written.
    """
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)

    rows: dict[str, dict] = {}
    if SNAPSHOT_PATH.exists():
        with open(SNAPSHOT_PATH, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                rows[row["week_start_date"]] = row
    rows[snapshot["week_start_date"]] = snapshot

    with open(SNAPSHOT_PATH, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for week in sorted(rows):
            writer.writerow(rows[week])


def main() -> None:
    """Computes the snapshot of the latest dump's week and writes it.

    Returns:
        None.

    Raises:
        SystemExit, ValueError: propagated from week_of_latest_dump().
        duckdb.Error, OSError: propagated from compute_snapshot() and
            write_row().
    """
    week = week_of_latest_dump()

    con = duckdb.connect(DB_PATH, read_only=True)
    snapshot = compute_snapshot(con, week)
    con.close()

    write_row(snapshot)

    print("--- Snapshot written ---")
    for key, value in snapshot.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    # No option today, but argparse still rejects an unknown or mistyped
    # argument instead of silently writing a row to the committed history.
    parser = argparse.ArgumentParser(
        description="Write the weekly market snapshot of the latest dump's week.",
        allow_abbrev=False,
    )
    parser.parse_args()
    main()
