import duckdb

con = duckdb.connect('../data/warehouse.duckdb', read_only=True)

# Croisement du remplissage des deux clés géographiques sur la population cible
q = con.execute("""
    select
        case when code_postal is null then 'CP absent' else 'CP présent' end as cp,
        case when commune is null then 'INSEE absent' else 'INSEE présent' end as insee,
        count(*) as nb
    from fct_offre
    where categorie_employeur = 'EMPLOYEUR_DIRECT'
    group by 1, 2
    order by 3 desc
""").fetchall()

print("Croisement code_postal / code INSEE (213 offres EMPLOYEUR_DIRECT) :")
for ligne in q:
    print(ligne)

con.close()