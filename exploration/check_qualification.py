"""
check_qualification.py

Goal: measure the is_data_job rule of fct_job_offer against 100 hand-labelled
listings (data/qualification_labels.csv), drawn at random from the 2026-10-05
pull. Prints the confusion counts, precision, recall and every disagreement.

The labels only exist for that pull: the warehouse must be built on the
versioned 2026-10-05 dump, otherwise the script stops.

Run: from france_data_market/ -> python3 ../exploration/check_qualification.py
"""

import csv
import sys

import duckdb

DB_PATH = "../data/warehouse.duckdb"
LABELS_PATH = "../data/qualification_labels.csv"


def load_labels():
    """Returns {job_offer_id: row} from the labels file."""
    with open(LABELS_PATH, newline="") as labels_file:
        return {row["job_offer_id"]: row for row in csv.DictReader(labels_file)}


def load_predictions(offer_ids):
    """Returns {job_offer_id: is_data_job} for the labelled offers."""
    con = duckdb.connect(DB_PATH, read_only=True)
    rows = con.execute(
        "select job_offer_id, is_data_job from fct_job_offer "
        "where job_offer_id in (select unnest(?))",
        [list(offer_ids)],
    ).fetchall()
    return dict(rows)


def main():
    labels = load_labels()
    predictions = load_predictions(labels)

    missing = len(labels) - len(predictions)
    if missing:
        sys.exit(f"{missing} labelled offers not in the warehouse: build it on the 2026-10-05 dump.")

    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    disagreements = []
    for offer_id, row in labels.items():
        label = row["is_data_job_label"] == "true"
        predicted = predictions[offer_id]
        key = ("t" if label == predicted else "f") + ("p" if predicted else "n")
        counts[key] += 1
        if label != predicted:
            disagreements.append((offer_id, row["job_title"], label, row["is_doubtful"]))

    precision = 100 * counts["tp"] / (counts["tp"] + counts["fp"])
    recall = 100 * counts["tp"] / (counts["tp"] + counts["fn"])
    print(counts)
    print(f"precision {precision:.1f}%, recall {recall:.1f}%")
    for offer_id, title, label, doubtful in disagreements:
        print(f"{offer_id} | {title} | label={label} | doubtful={doubtful}")


if __name__ == "__main__":
    main()
