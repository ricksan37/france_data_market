"""
check_masque_coherence.py

Objectif : expliquer l'écart entre le pattern texte "notre client" (29/208)
et end_client_masked=true (21/208, mesuré) avant toute décision d'architecture.
Vérifie aussi la nature des 178 NULL.

Lancement : depuis france_data_market/ -> python3 ../exploration/check_masque_coherence.py
"""

import duckdb

CHEMIN_DB = "../data/warehouse.duckdb"
con = duckdb.connect(CHEMIN_DB, read_only=True)

print("--- A. Les 178 NULL : extraction_status associé ---")
res = con.execute("""
    select extraction_status, count(*) as nb
    from stg_extraction__skills
    where end_client_masked is null
    group by extraction_status
""").fetchall()
for statut, nb in res:
    print(f"  {statut} : {nb}")

print("\n--- B. Sur les ANONYME : pattern texte 'notre client' vs champ structuré ---")
res = con.execute("""
    select
        s.end_client_masked,
        f.job_description ilike '%notre client%' as pattern_texte,
        count(*) as nb
    from int_employer_classification c
    join stg_extraction__skills s on c.job_offer_id = s.job_offer_id
    join stg_raw__ft_job_offers f on c.job_offer_id = f.job_offer_id
    where c.employer_category = 'ANONYMOUS'
    group by s.end_client_masked, f.job_description ilike '%notre client%'
    order by nb desc
""").fetchall()
for masque, pattern, nb in res:
    print(f"  masque={masque} | pattern='notre client'={pattern} : {nb}")

con.close()