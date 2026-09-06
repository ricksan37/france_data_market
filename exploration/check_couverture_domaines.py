"""
check_couverture_domaines.py

Objectif : lire le taux de couverture réel du mapping_domaines (mesuré à
19,7%), pour vérifier s'il a dérivé avant de rouvrir la
décision de ne pas mapper la longue traîne.

Lancement : depuis observatoire/ -> python3 ../exploration/check_couverture_domaines.py
"""

import duckdb

CHEMIN_DB = "../data/warehouse.duckdb"
con = duckdb.connect(CHEMIN_DB, read_only=True)

res = con.execute("""
    select
        count(*) as total_mentions,
        count(case when domaine_brut != domaine_normalise
                   or domaine_brut in (select variante from mapping_domaines)
              then 1 end) as mentions_couvertes,
        round(100.0 * count(case when domaine_brut != domaine_normalise
                   or domaine_brut in (select variante from mapping_domaines)
              then 1 end) / count(*), 1) as taux_couverture_pct
    from fct_offre_domaine
""").fetchone()

total, couvertes, taux = res
print(f"  Total mentions   : {total}")
print(f"  Mentions couvertes : {couvertes}")
print(f"  Taux couverture  : {taux}%")
print(f"  Attendu           : 19.7%")

con.close()