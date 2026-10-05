"""
check_repartition_categorie.py

Goal: check after dbt build that the actual distribution of employer_category
matches the expected figure measured during exploration (187 ANONYMOUS, 21
INTERMEDIAIRE_reclasse, total unchanged at 552).

Run: from france_data_market/ -> python3 ../exploration/check_repartition_categorie.py
"""

import duckdb

CHEMIN_DB = "../data/warehouse.duckdb"
con = duckdb.connect(CHEMIN_DB, read_only=True)

res = con.execute("""
    select employer_category, count(*) as nb
    from int_employers_classified
    group by employer_category
    order by nb desc
""").fetchall()

total = 0
for cat, nb in res:
    print(f"  {cat} : {nb}")
    total += nb
print(f"  TOTAL : {total}")

con.close()