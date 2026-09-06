import duckdb

con = duckdb.connect('../data/warehouse.duckdb', read_only=True)

print("--- Répartition globale ---")
print(con.sql("""
    SELECT employer_category, COUNT(*) AS n
    FROM int_employer_classification
    GROUP BY employer_category
    ORDER BY n DESC
"""))

print("--- Exemples classés INTERMEDIAIRE ---")
print(con.sql("""
    SELECT s.employer_name_raw, s.naf_code_on_offer, c.employer_category
    FROM stg_raw__ft_job_offers s
    JOIN int_employer_classification c ON s.job_offer_id = c.job_offer_id
    WHERE c.employer_category = 'INTERMEDIARY'
    ORDER BY s.employer_name_raw
    LIMIT 20
"""))

print("--- Contrôle ANONYME : le nom est-il vraiment toujours NULL ? ---")
print(con.sql("""
    SELECT s.employer_name_raw, s.naf_code_on_offer, c.employer_category
    FROM stg_raw__ft_job_offers s
    JOIN int_employer_classification c ON s.job_offer_id = c.job_offer_id
    WHERE c.employer_category = 'ANONYMOUS' AND s.employer_name_raw IS NOT NULL
"""))