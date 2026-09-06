"""
check_volume_bornes_salariales.py

Objectif : vérifier si le volume horaire/mensuel a évolué depuis la mesure
initiale (19 offres horaires, 1 mensuelle) avant de statuer sur la
dette différée des bornes de plausibilité salariale.

Lancement : depuis observatoire/ -> python3 ../exploration/check_volume_bornes_salariales.py
"""

import duckdb

CHEMIN_DB = "../data/warehouse.duckdb"
con = duckdb.connect(CHEMIN_DB, read_only=True)

print("--- Répartition salaire_periode sur int_offres_salaire ---")
res = con.execute("""
    select salaire_periode, count(*) as nb
    from int_offres_salaire
    where salaire_periode = 'horaire'
        or salaire_periode = 'mensuel'
        or salaire_periode = 'annuel'
    group by salaire_periode
    order by nb desc
""").fetchall()
for periode, nb in res:
    print(f"  {periode} : {nb}")

con.close()