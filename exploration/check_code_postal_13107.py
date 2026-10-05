"""
check_code_postal_13107.py

Goal: identify the offer carrying postal code 13107, absent from the official
reference (Marseille arrondissements: 13001-13016 only), before deciding
whether it is an isolated typo or a real source problem.

Run: from france_data_market/ -> python3 ../exploration/check_code_postal_13107.py
"""

import duckdb

CHEMIN_DB = "../data/warehouse.duckdb"
con = duckdb.connect(CHEMIN_DB, read_only=True)

res = con.execute("""
    select job_offer_id, postal_code, commune_code, employer_name
    from fct_job_offer
    where postal_code = '13107'
""").df()

print(res)

con.close()