# exploration/check_rome_candidates.py
"""
Measures candidate ROME codes before changing the collection scope.

For each code: the total announced by the API (Content-Range) and a sample
of offer titles, to judge by eye whether the code is really a data job or
also catches unrelated offers (recruiters pick the code themselves, so a
BI code can hold business developer offers).

Run from the project root: python3 exploration/check_rome_candidates.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # import auth/search from the root

from auth import get_access_token
from search import get_all_offers

# Candidates spotted in the ROME reference table (June 2026), with the
# appellation that made them candidates.
CANDIDATES = [
    ("M1419", "Data analyst"),
    ("M1851", "Analyste décisionnel - Business Intelligence"),
    ("M1872", "Consultant décisionnel - Business Intelligence"),
    ("M1824", "Développeur décisionnel - Business Intelligence"),
    ("M1868", "Architecte base de données / Data architect"),
    ("M1889", "Ingénieur IA / Machine learning"),
    ("M1894", "Administrateur de bases de données"),
    ("M1414", "Statisticien"),
    ("M1423", "Chief Data Officer"),
]

SAMPLE_SIZE = 12

if __name__ == "__main__":
    token, _ = get_access_token()
    for code, label in CANDIDATES:
        offers, total = get_all_offers({"codeROME": code}, token=token)
        print(f"\n=== {code} ({label}): {total} offers")
        for offer in offers[:SAMPLE_SIZE]:
            print(f"   - {offer['intitule']}")
