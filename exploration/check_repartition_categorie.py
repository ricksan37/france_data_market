"""
check_repartition_categorie.py

Objectif : vérifier après dbt build que la répartition réelle de
employer_category correspond au chiffre attendu mesuré en exploration
(187 ANONYME, 21 INTERMEDIAIRE_reclasse, total inchangé à 552).

Lancement : depuis france_data_market/ -> python3 ../exploration/check_repartition_categorie.py
"""

import duckdb

CHEMIN_DB = "../data/warehouse.duckdb"
con = duckdb.connect(CHEMIN_DB, read_only=True)

res = con.execute("""
    select employer_category, count(*) as nb
    from int_employer_classification
    group by employer_category
    order by nb desc
""").fetchall()

total = 0
for cat, nb in res:
    print(f"  {cat} : {nb}")
    total += nb
print(f"  TOTAL : {total}")

con.close()