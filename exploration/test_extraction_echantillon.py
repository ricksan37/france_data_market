"""
Validation du prompt sur un échantillon avant le run complet.

Pourquoi un échantillon : le prompt n'a été validé que sur UNE offre, riche et
bien structurée (Opteven). Les 552 offres contiennent des cas très différents :
annonces courtes, offres non-data mal taguées par ROME (limite connue),
annonces d'intermédiaires sans aucune technologie. Vingt offres coûtent 4 minutes
et évitent de découvrir un défaut systématique après 1h45 de calcul.

L'échantillon est tiré avec un ordre déterministe (order by offre_id) plutôt
qu'aléatoire : deux exécutions doivent porter sur les mêmes offres, sinon on ne
peut pas comparer l'effet d'un changement de prompt.

ATTENTION : stg_ft_offres est une vue -> lancement depuis observatoire/.

Lancement : depuis observatoire/  ->  python3 ../exploration/test_extraction_echantillon.py
"""

import sys
import time

import duckdb
from ollama import chat

sys.path.insert(0, "../exploration")
from schema_extraction import ExtractionOffre
from test_extraction_une_offre import PROMPT, MODELE, CHEMIN_DB

TAILLE_ECHANTILLON = 20


def main() -> None:
    con = duckdb.connect(CHEMIN_DB, read_only=True)
    offres = con.execute(f"""
        select offre_id, intitule, description
        from stg_ft_offres
        order by offre_id
        limit {TAILLE_ECHANTILLON}
    """).fetchall()
    con.close()

    print(f"Echantillon : {len(offres)} offres\n")

    debut_total = time.time()
    echecs = []

    for i, (offre_id, intitule, description) in enumerate(offres, 1):
        debut = time.time()
        try:
            reponse = chat(
                model=MODELE,
                messages=[{"role": "user",
                           "content": PROMPT.format(description=description)}],
                format=ExtractionOffre.model_json_schema(),
                options={"temperature": 0},
                think=False,
            )
            extraction = ExtractionOffre.model_validate_json(reponse.message.content)
            duree = time.time() - debut

            print(f"[{i:2}/{len(offres)}] {offre_id} ({intitule[:45]})")
            print(f"        {duree:5.1f}s | techs: {len(extraction.technologies):2} "
                  f"| domaines: {len(extraction.domaines):2} "
                  f"| etudes: {extraction.niveau_etudes} "
                  f"| exp: {extraction.annees_experience_min}")
            print(f"        techs = {extraction.technologies}")
            print(f"        domaines = {extraction.domaines}")

        except Exception as err:
            # Un échec de validation est un fait à compter, pas une raison
            # d'interrompre : on veut connaître le TAUX d'échec sur l'échantillon.
            echecs.append((offre_id, str(err)[:120]))
            print(f"[{i:2}/{len(offres)}] {offre_id} -> ECHEC : {str(err)[:120]}")

    duree_totale = time.time() - debut_total
    moyenne = duree_totale / len(offres)

    print(f"\n{'=' * 70}")
    print(f"Duree totale      : {duree_totale:.1f}s")
    print(f"Moyenne par offre : {moyenne:.1f}s")
    print(f"Projection 552    : {moyenne * 552 / 60:.0f} minutes")
    print(f"Echecs            : {len(echecs)}/{len(offres)}")
    for offre_id, err in echecs:
        print(f"   {offre_id} : {err}")


if __name__ == "__main__":
    main()