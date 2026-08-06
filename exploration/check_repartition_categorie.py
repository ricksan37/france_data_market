"""
check_repartition_categorie.py

Objectif : vérifier après dbt build que la répartition réelle de
categorie_employeur correspond au chiffre attendu mesuré en exploration
(187 ANONYME, 21 INTERMEDIAIRE_reclasse, total inchangé à 552).

Lancement : depuis observatoire/ -> python3 ../exploration/check_repartition_categorie.py
"""

import duckdb

CHEMIN_DB = "../data/warehouse.duckdb"
con = duckdb.connect(CHEMIN_DB, read_only=True)

res = con.execute("""
    select categorie_employeur, count(*) as nb
    from int_classification_employeur
    group by categorie_employeur
    order by nb desc
""").fetchall()

total = 0
for cat, nb in res:
    print(f"  {cat} : {nb}")
    total += nb
print(f"  TOTAL : {total}")

con.close()