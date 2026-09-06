"""
check_volume_bornes_salariales.py

Objectif : vérifier si le volume horaire/mensuel a évolué depuis la mesure
initiale (19 offres horaires, 1 mensuelle) avant de statuer sur la
dette différée des bornes de plausibilité salariale.

Lancement : depuis france_data_market/ -> python3 ../exploration/check_volume_bornes_salariales.py
"""

import duckdb

CHEMIN_DB = "../data/warehouse.duckdb"
con = duckdb.connect(CHEMIN_DB, read_only=True)

print("--- Répartition salary_period sur int_job_offer_salary ---")
res = con.execute("""
    select salary_period, count(*) as nb
    from int_job_offer_salary
    where salary_period = 'horaire'
        or salary_period = 'mensuel'
        or salary_period = 'annual'
    group by salary_period
    order by nb desc
""").fetchall()
for periode, nb in res:
    print(f"  {periode} : {nb}")

con.close()