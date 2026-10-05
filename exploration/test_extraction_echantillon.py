"""
Prompt validation on a sample before the full run.

Why a sample: the prompt was only validated on ONE offer, rich and well
structured (Opteven). The 552 offers contain very different cases: short ads,
non-data offers badly tagged by ROME (known limit), intermediary ads without
any technology. Twenty offers cost 4 minutes and avoid discovering a
systematic flaw after 1h45 of compute.

The sample is drawn in a deterministic order (order by job_offer_id) rather
than at random: two runs must cover the same offers, otherwise the effect of
a prompt change cannot be compared.

WARNING: stg_raw__ft_job_offers is a view -> run from france_data_market/.

Run: from france_data_market/  ->  python3 ../exploration/test_extraction_echantillon.py
"""

import sys
import time

import duckdb
from ollama import chat

sys.path.insert(0, "..")
from schema_extraction import ExtractionOffre
from test_extraction_une_offre import PROMPT, MODELE, CHEMIN_DB

TAILLE_ECHANTILLON = 20


def main() -> None:
    con = duckdb.connect(CHEMIN_DB, read_only=True)
    offres = con.execute(f"""
        select job_offer_id, job_title, job_description
        from stg_raw__ft_job_offers
        order by job_offer_id
        limit {TAILLE_ECHANTILLON}
    """).fetchall()
    con.close()

    print(f"Echantillon : {len(offres)} offres\n")

    debut_total = time.time()
    echecs = []

    for i, (job_offer_id, job_title, description) in enumerate(offres, 1):
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

            print(f"[{i:2}/{len(offres)}] {job_offer_id} ({job_title[:45]})")
            print(f"        {duree:5.1f}s | techs: {len(extraction.technologies):2} "
                  f"| domaines: {len(extraction.domaines):2} "
                  f"| etudes: {extraction.niveau_etudes} "
                  f"| exp: {extraction.annees_experience_min}")
            print(f"        techs = {extraction.technologies}")
            print(f"        domaines = {extraction.domaines}")

        except Exception as err:
            # A validation failure is a fact to count, not a reason to stop:
            # we want to know the failure RATE on the sample.
            echecs.append((job_offer_id, str(err)[:120]))
            print(f"[{i:2}/{len(offres)}] {job_offer_id} -> ECHEC : {str(err)[:120]}")

    duree_totale = time.time() - debut_total
    moyenne = duree_totale / len(offres)

    print(f"\n{'=' * 70}")
    print(f"Duree totale      : {duree_totale:.1f}s")
    print(f"Moyenne par offre : {moyenne:.1f}s")
    print(f"Projection 552    : {moyenne * 552 / 60:.0f} minutes")
    print(f"Echecs            : {len(echecs)}/{len(offres)}")
    for job_offer_id, err in echecs:
        print(f"   {job_offer_id} : {err}")


if __name__ == "__main__":
    main()