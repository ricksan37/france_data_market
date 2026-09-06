"""
check_fct_offre_reclasse.py

Objectif : vérifier que fct_offre.entreprise_nom est bien rempli sur les 21
offres INTERMEDIAIRE_reclasse (chiffre attendu), et vide
nulle part ailleurs par erreur.

Lancement : depuis observatoire/ -> python3 ../exploration/check_fct_offre_reclasse.py
"""

import duckdb

CHEMIN_DB = "../data/warehouse.duckdb"
con = duckdb.connect(CHEMIN_DB, read_only=True)

print("--- Répartition entreprise_nom rempli/vide par categorie_employeur ---")
res = con.execute("""
    select
        categorie_employeur,
        count(*) as total,
        count(entreprise_nom) as nom_rempli
    from fct_offre
    group by categorie_employeur
    order by total desc
""").fetchall()
for cat, total, rempli in res:
    print(f"  {cat} : {rempli}/{total} avec entreprise_nom rempli")

con.close()