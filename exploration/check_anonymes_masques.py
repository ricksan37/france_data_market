"""
check_anonymes_masques.py

Objectif : mesurer le volume d'offres ANONYME reclassifiables en INTERMEDIAIRE
via client_final_masque (Phase 4), avant d'écrire la moindre logique de
reclassification dans int_classification_employeur.

Lancement : depuis observatoire/ -> python3 ../exploration/check_anonymes_masques.py
"""

import duckdb

CHEMIN_DB = "../data/warehouse.duckdb"

con = duckdb.connect(CHEMIN_DB, read_only=True)

print("--- 1. Répartition de client_final_masque sur les 552 offres ---")
res = con.execute("""
    select client_final_masque, count(*) as nb
    from stg_offres_skills
    group by client_final_masque
    order by nb desc
""").fetchall()
for masque, nb in res:
    print(f"  {masque} : {nb}")

print("\n--- 2. ANONYME avec client_final_masque = true ---")
nb_reclassifiables = con.execute("""
    select count(*)
    from int_classification_employeur c
    join stg_offres_skills s on c.offre_id = s.offre_id
    where c.categorie_employeur = 'ANONYME'
    and s.client_final_masque = true
""").fetchone()[0]
print(f"  {nb_reclassifiables}")

print("\n--- 3. Parmi eux, entreprise_nom_texte renseigné ---")
nb_avec_nom = con.execute("""
    select count(*)
    from int_classification_employeur c
    join stg_offres_skills s on c.offre_id = s.offre_id
    where c.categorie_employeur = 'ANONYME'
    and s.client_final_masque = true
    and s.entreprise_nom_texte is not null
    and trim(s.entreprise_nom_texte) != ''
""").fetchone()[0]
print(f"  {nb_avec_nom}")

print("\n--- 4. Nouveau total ANONYME après reclassification ---")
total_anonyme = con.execute("""
    select count(*)
    from int_classification_employeur
    where categorie_employeur = 'ANONYME'
""").fetchone()[0]
nouveau_total = total_anonyme - nb_reclassifiables
print(f"  Actuel   : {total_anonyme}")
print(f"  Nouveau  : {nouveau_total}")
print(f"  Écart    : -{nb_reclassifiables}")

con.close()