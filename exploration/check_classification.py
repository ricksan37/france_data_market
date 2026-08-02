import duckdb

con = duckdb.connect('../data/warehouse.duckdb', read_only=True)

print("--- Répartition globale ---")
print(con.sql("""
    SELECT categorie_employeur, COUNT(*) AS n
    FROM int_classification_employeur
    GROUP BY categorie_employeur
    ORDER BY n DESC
"""))

print("--- Exemples classés INTERMEDIAIRE ---")
print(con.sql("""
    SELECT s.entreprise_nom, s.code_naf, c.categorie_employeur
    FROM stg_ft_offres s
    JOIN int_classification_employeur c ON s.offre_id = c.offre_id
    WHERE c.categorie_employeur = 'INTERMEDIAIRE'
    ORDER BY s.entreprise_nom
    LIMIT 20
"""))

print("--- Contrôle ANONYME : le nom est-il vraiment toujours NULL ? ---")
print(con.sql("""
    SELECT s.entreprise_nom, s.code_naf, c.categorie_employeur
    FROM stg_ft_offres s
    JOIN int_classification_employeur c ON s.offre_id = c.offre_id
    WHERE c.categorie_employeur = 'ANONYME' AND s.entreprise_nom IS NOT NULL
"""))