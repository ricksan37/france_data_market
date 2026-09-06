import duckdb

con = duckdb.connect('../data/warehouse.duckdb', read_only=True)

# Croisement du remplissage des deux clés géographiques sur la population cible
q = con.execute("""
    select
        case when postal_code is null then 'CP absent' else 'CP présent' end as cp,
        case when commune_code is null then 'INSEE absent' else 'INSEE présent' end as insee,
        count(*) as nb
    from fct_job_offer
    where employer_category = 'DIRECT_EMPLOYER'
    group by 1, 2
    order by 3 desc
""").fetchall()

print("Croisement postal_code / code INSEE (213 offres DIRECT_EMPLOYER) :")
for ligne in q:
    print(ligne)

con.close()