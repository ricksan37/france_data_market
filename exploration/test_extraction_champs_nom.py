"""
Test cible des deux nouveaux champs (entreprise_nom_texte, client_final_masque)
sur 4 offres à vérité terrain déjà lue manuellement (S6).

Attendu :
  5076918 (Framatome)  -> nom="Framatome", masque=False (parle d'elle-même)
  4893934 (CIMPA)       -> nom="CIMPA", masque=True (accompagne Airbus)
  4888800 (Wavestone)   -> nom="Wavestone", masque=False (parle d'elle-même)
  4319968 (BRAINLOGIC)  -> nom="BRAINLOGIC", masque=True (accompagne un client)

Lancement : depuis observatoire/ -> python3 ../exploration/test_extraction_champs_nom.py
"""

import sys

import duckdb
from ollama import chat

sys.path.insert(0, "../exploration")
from schema_extraction import ExtractionOffre
from test_extraction_une_offre import PROMPT, MODELE, CHEMIN_DB

OFFRES_TEST = {
    "5076918": ("Framatome", False),
    "4893934": ("CIMPA", True),
    "4888800": ("Wavestone", False),
    "4319968": ("BRAINLOGIC", True),
}


def main() -> None:
    con = duckdb.connect(CHEMIN_DB, read_only=True)

    for offre_id, (nom_attendu, masque_attendu) in OFFRES_TEST.items():
        row = con.execute(
            "select description from fct_offre where offre_id = ?", [offre_id]
        ).fetchone()
        if row is None:
            print(f"[{offre_id}] INTROUVABLE dans fct_offre")
            continue
        description = row[0]

        reponse = chat(
            model=MODELE,
            messages=[{"role": "user",
                       "content": PROMPT.format(description=description)}],
            options={"temperature": 0},
            format=ExtractionOffre.model_json_schema(),
        )
        extraction = ExtractionOffre.model_validate_json(reponse.message.content)

        ok_nom = "OK" if extraction.entreprise_nom_texte == nom_attendu else "ECART"
        ok_masque = "OK" if extraction.client_final_masque == masque_attendu else "ECART"

        print(f"[{offre_id}]")
        print(f"  nom_texte : {extraction.entreprise_nom_texte!r:30} "
              f"(attendu {nom_attendu!r}) -> {ok_nom}")
        print(f"  masque    : {extraction.client_final_masque!r:30} "
              f"(attendu {masque_attendu!r}) -> {ok_masque}")

    con.close()


if __name__ == "__main__":
    main()