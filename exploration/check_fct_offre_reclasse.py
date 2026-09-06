"""
check_fct_offre_reclasse.py

Objectif : vérifier que fct_job_offer.employer_name est bien rempli sur les 21
offres INTERMEDIAIRE_reclasse (chiffre attendu), et vide
nulle part ailleurs par erreur.

Lancement : depuis france_data_market/ -> python3 ../exploration/check_fct_offre_reclasse.py
"""

import duckdb

CHEMIN_DB = "../data/warehouse.duckdb"
con = duckdb.connect(CHEMIN_DB, read_only=True)

print("--- Répartition employer_name rempli/vide par employer_category ---")
res = con.execute("""
    select
        employer_category,
        count(*) as total,
        count(employer_name) as nom_rempli
    from fct_job_offer
    group by employer_category
    order by total desc
""").fetchall()
for cat, total, rempli in res:
    print(f"  {cat} : {rempli}/{total} avec employer_name rempli")

con.close()