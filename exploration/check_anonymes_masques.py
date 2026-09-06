"""
check_anonymes_masques.py

Objectif : mesurer le volume d'offres ANONYME reclassifiables en INTERMEDIAIRE
via end_client_masked (Phase 4), avant d'écrire la moindre logique de
reclassification dans int_employer_classification.

Lancement : depuis france_data_market/ -> python3 ../exploration/check_anonymes_masques.py
"""

import duckdb

CHEMIN_DB = "../data/warehouse.duckdb"

con = duckdb.connect(CHEMIN_DB, read_only=True)

print("--- 1. Répartition de end_client_masked sur les 552 offres ---")
res = con.execute("""
    select end_client_masked, count(*) as nb
    from stg_extraction__skills
    group by end_client_masked
    order by nb desc
""").fetchall()
for masque, nb in res:
    print(f"  {masque} : {nb}")

print("\n--- 2. ANONYME avec end_client_masked = true ---")
nb_reclassifiables = con.execute("""
    select count(*)
    from int_employer_classification c
    join stg_extraction__skills s on c.job_offer_id = s.job_offer_id
    where c.employer_category = 'ANONYMOUS'
    and s.end_client_masked = true
""").fetchone()[0]
print(f"  {nb_reclassifiables}")

print("\n--- 3. Parmi eux, employer_name_text renseigné ---")
nb_avec_nom = con.execute("""
    select count(*)
    from int_employer_classification c
    join stg_extraction__skills s on c.job_offer_id = s.job_offer_id
    where c.employer_category = 'ANONYMOUS'
    and s.end_client_masked = true
    and s.employer_name_text is not null
    and trim(s.employer_name_text) != ''
""").fetchone()[0]
print(f"  {nb_avec_nom}")

print("\n--- 4. Nouveau total ANONYME après reclassification ---")
total_anonyme = con.execute("""
    select count(*)
    from int_employer_classification
    where employer_category = 'ANONYMOUS'
""").fetchone()[0]
nouveau_total = total_anonyme - nb_reclassifiables
print(f"  Actuel   : {total_anonyme}")
print(f"  Nouveau  : {nouveau_total}")
print(f"  Écart    : -{nb_reclassifiables}")

con.close()