"""
check_code_postal_13107.py

Objectif : identifier l'offre portant le code postal 13107, absent du
référentiel officiel (arrondissements marseillais : 13001-13016 uniquement),
avant de décider si c'est une coquille isolée ou un vrai souci de source.

Lancement : depuis france_data_market/ -> python3 ../exploration/check_code_postal_13107.py
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