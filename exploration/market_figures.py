"""
market_figures.py

Goal: recompute the figures of findings 1 and 5 to 7 of the README: offer exits
after four weeks, then roles, stack, contracts and geography on the qualified
listings (is_data_job). Read-only.

The figures describe the 2026-10-05 pull: the warehouse must be built on the
versioned dump of that date, and data/snapshots/offer_presence.csv must hold
the week of 2026-11-02.

Run: from france_data_market/ -> python3 ../exploration/market_figures.py
"""

import csv
from collections import defaultdict

import duckdb

DB_PATH = "../data/warehouse.duckdb"
PRESENCE_PATH = "../data/snapshots/offer_presence.csv"
BASE_WEEK = "2026-10-05"
EXIT_WEEKS = ["2026-10-12", "2026-10-19", "2026-10-26", "2026-11-02"]

ROLES = {
    "data engineer": r"data[ -]?engineer|ing[ée]nieur(e)?( de| en)? (la )?(data|donn[ée]es)",
    "data analyst": r"data[ -]?analy|analyste (de )?(data|donn)",
    "data scientist": r"data[ -]?scien",
    "analytics engineer": r"analytics?[ -]engineer",
}
TOOLS = {
    "SQL": r"\bsql\b",
    "Python": r"\bpython\b",
    "Power BI": r"power ?bi",
    "dbt": r"\bdbt\b",
    "GCP": r"\bgcp\b|google cloud",
    "Azure": r"\bazure\b",
    "AWS": r"\baws\b",
    "Snowflake": r"snowflake",
    "Databricks": r"databricks",
    "BigQuery": r"bigquery|big query",
}
ILE_DE_FRANCE = ("75", "77", "78", "91", "92", "93", "94", "95")

QUALIFIED = "from fct_job_offer where is_canonical_listing and is_data_job"


def load_presence():
    """Returns {week_start_date: set of job_offer_id}."""
    presence = defaultdict(set)
    with open(PRESENCE_PATH, newline="") as presence_file:
        for row in csv.DictReader(presence_file):
            presence[row["week_start_date"]].add(row["job_offer_id"])
    return presence


def exit_rate(offer_ids, still_present):
    """Returns the share of offer_ids missing from still_present, in percent."""
    return round(100 * sum(i not in still_present for i in offer_ids) / len(offer_ids), 1)


def print_exits(con, presence):
    """Prints finding 1: exits by week, then after four weeks by employer."""
    base = presence[BASE_WEEK]
    print(len(base), "offers on", BASE_WEEK)
    print("exits:", [exit_rate(base, presence[week]) for week in EXIT_WEEKS])

    rows = con.execute(
        "select job_offer_id, "
        "case when lower(employer_name) = 'collective.work' then 'Collective.work' "
        "when employer_category = 'INTERMEDIARY_RECLASSIFIED' then 'ANONYMOUS' "
        "else employer_category end from fct_job_offer"
    ).fetchall()
    groups = defaultdict(list)
    for offer_id, group in rows:
        groups[group].append(offer_id)
    for group, offer_ids in sorted(groups.items()):
        print(group, len(offer_ids), exit_rate(offer_ids, presence[EXIT_WEEKS[-1]]))


def print_shares(con, column, patterns, total):
    """Prints the share of qualified listings whose column matches each pattern."""
    for name, pattern in patterns.items():
        count = con.execute(
            f"select count(*) {QUALIFIED} and regexp_matches(lower({column}), ?)", [pattern]
        ).fetchone()[0]
        print(name, count, round(100 * count / total, 1))


def main():
    con = duckdb.connect(DB_PATH, read_only=True)
    print_exits(con, load_presence())

    total = con.execute(f"select count(*) {QUALIFIED}").fetchone()[0]
    print(total, "qualified listings")
    print_shares(con, "job_title", ROLES, total)
    print_shares(con, "job_description", TOOLS, total)

    contracts = con.execute(
        f"select contract_type, count(*) {QUALIFIED} group by 1 order by 2 desc"
    ).fetchall()
    print([(name, round(100 * count / total, 1)) for name, count in contracts])

    communes = [row[0] for row in con.execute(f"select commune_code {QUALIFIED}").fetchall()]
    known = [code for code in communes if code]
    print("no commune:", len(communes) - len(known))
    print("Paris:", round(100 * sum(c == "75056" or c.startswith("751") for c in known) / total, 1))
    print("Ile-de-France:", round(100 * sum(c[:2] in ILE_DE_FRANCE for c in known) / total, 1))


if __name__ == "__main__":
    main()
