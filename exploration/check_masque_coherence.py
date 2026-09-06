"""
check_masque_coherence.py

Objectif : expliquer l'écart entre le pattern texte "notre client" (29/208)
et client_final_masque=true (21/208, mesuré) avant toute décision d'architecture.
Vérifie aussi la nature des 178 NULL.

Lancement : depuis observatoire/ -> python3 ../exploration/check_masque_coherence.py
"""

import duckdb

CHEMIN_DB = "../data/warehouse.duckdb"
con = duckdb.connect(CHEMIN_DB, read_only=True)

print("--- A. Les 178 NULL : statut_extraction associé ---")
res = con.execute("""
    select statut_extraction, count(*) as nb
    from stg_offres_skills
    where client_final_masque is null
    group by statut_extraction
""").fetchall()
for statut, nb in res:
    print(f"  {statut} : {nb}")

print("\n--- B. Sur les ANONYME : pattern texte 'notre client' vs champ structuré ---")
res = con.execute("""
    select
        s.client_final_masque,
        f.description ilike '%notre client%' as pattern_texte,
        count(*) as nb
    from int_classification_employeur c
    join stg_offres_skills s on c.offre_id = s.offre_id
    join stg_ft_offres f on c.offre_id = f.offre_id
    where c.categorie_employeur = 'ANONYME'
    group by s.client_final_masque, f.description ilike '%notre client%'
    order by nb desc
""").fetchall()
for masque, pattern, nb in res:
    print(f"  masque={masque} | pattern='notre client'={pattern} : {nb}")

con.close()