"""
check_couverture_domaines.py

Goal: read the actual coverage rate of mapping_domaines (measured at 19.7%),
to check whether it has drifted before reopening the decision not to map the
long tail.

Run: from france_data_market/ -> python3 ../exploration/check_couverture_domaines.py
"""

import duckdb

CHEMIN_DB = "../data/warehouse.duckdb"
con = duckdb.connect(CHEMIN_DB, read_only=True)

res = con.execute("""
    select
        count(*) as total_mentions,
        count(case when raw_domain != normalized_domain
                   or raw_domain in (select variant from mapping_domaines)
              then 1 end) as mentions_couvertes,
        round(100.0 * count(case when raw_domain != normalized_domain
                   or raw_domain in (select variant from mapping_domaines)
              then 1 end) / count(*), 1) as taux_couverture_pct
    from fct_job_offer_domain
""").fetchone()

total, couvertes, taux = res
print(f"  Total mentions   : {total}")
print(f"  Mentions couvertes : {couvertes}")
print(f"  Taux couverture  : {taux}%")
print(f"  Attendu           : 19.7%")

con.close()