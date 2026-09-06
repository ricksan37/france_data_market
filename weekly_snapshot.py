"""
weekly_snapshot.py

Goal: compute a weekly market snapshot and append it to
data/snapshots/weekly_market.csv, the only artifact persisted between two CI
runs (warehouse.duckdb and the JSON dumps stay ephemeral/gitignored).

In CI_WITHOUT_EXTRACTION mode (GitHub Actions workflow), fct_job_offer_technology
is empty -- top_technology is then "not available (CI)" rather than crashing
on an empty fetchone().

Usage: from the repo root -> python3 weekly_snapshot.py
"""

import csv
from datetime import date, timedelta
from pathlib import Path

import duckdb

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


def monday_of_the_week() -> str:
    """Snapshot key: the Monday of the ISO week, not the run date.

    date.today() used to be the key: three manual triggers on 2026-08-09
    produced three distinct rows for the same week, a grain
    fct_weekly_market would have inherited broken. The Monday stays a date
    axis directly usable in a chart, unlike a "2026-W32" notation.
    """
    today = date.today()
    return (today - timedelta(days=today.weekday())).isoformat()


def compute_snapshot(con: duckdb.DuckDBPyConnection) -> dict:
    """Computes today's metrics on the current state of fct_job_offer."""

    total_count = con.execute("select count(*) from fct_job_offer").fetchone()[0]

    count_by_category = dict(con.execute("""
        select employer_category, count(*)
        from fct_job_offer
        group by employer_category
    """).fetchall())

    median_salary = con.execute("""
        select median(salary_min)
        from fct_job_offer
        where salary_period = 'annual'
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
        "week_start_date": monday_of_the_week(),
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
        # re-read downstream (same choice as top_technology, more robust).
        # Without this column, a week with no LLM fields would be
        # indistinguishable from a week where the LLM found nothing.
        "llm_extraction_available": bool(top_technology_result),
    }


def write_row(snapshot: dict) -> None:
    """Upsert by week: one week = one row, the latest write wins.

    The old append-only mode left three rows for 2026-08-09 (two
    workflow_dispatch tests plus the real run). Rewriting the whole file
    costs a few kilobytes and guarantees grain uniqueness at the source,
    rather than catching it downstream with a qualify in every consuming
    model.

    A mid-week rerun therefore overwrites that week's row: this is
    intentional, the most recent measurement is the right one. A local run
    (LLM fields populated) thus takes precedence over Monday's CI run, and
    llm_extraction_available traces which of the two produced the row.
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
    con = duckdb.connect(DB_PATH, read_only=True)
    snapshot = compute_snapshot(con)
    con.close()

    write_row(snapshot)

    print("--- Snapshot added ---")
    for key, value in snapshot.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
