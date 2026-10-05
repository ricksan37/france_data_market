"""
check_volume_bornes_salariales.py

Goal: check whether the hourly/monthly volume has changed since the initial
measurement (19 hourly offers, 1 monthly) before ruling on the deferred debt
of the salary plausibility bounds.

Run: from france_data_market/ -> python3 ../exploration/check_volume_bornes_salariales.py
"""

import duckdb

CHEMIN_DB = "../data/warehouse.duckdb"
con = duckdb.connect(CHEMIN_DB, read_only=True)

print("--- Répartition salary_period sur int_job_offer_salary_parsed ---")
res = con.execute("""
    select salary_period, count(*) as nb
    from int_job_offer_salary_parsed
    where salary_period = 'horaire'
        or salary_period = 'mensuel'
        or salary_period = 'annual'
    group by salary_period
    order by nb desc
""").fetchall()
for periode, nb in res:
    print(f"  {periode} : {nb}")

con.close()