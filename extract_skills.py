"""
Skill extraction from job offer text.

Replicates the ingestion pattern established in Phase 1 and Phase 3: Python
script -> timestamped JSON dump in data/raw/ -> dbt source -> stg_ model. dbt
makes no LLM calls, just as it makes no HTTP calls.

MODEL CHOSEN: mistral-nemo (12B), after a measured comparison on a 20-offer
sample against mistral 7B and qwen3 8B. Decisive criterion: only Nemo
correctly distinguishes a named product (Azure, Databricks) from a technical
concept (RAG, CI/CD, Data Lake): an irreducible defect via prompting on both
7-8B models, tested across three successive phrasings.

KNOWN AND ACCEPTED LIMIT: Nemo under-extracts the 'domaines' field on
consulting listings. Measured: 4 concepts found out of ~8 present in the
text (offer 0388930). Not fixed: a further prompt iteration produced a
marginal gain on 'domaines' at the cost of a hallucination on
annees_experience_min. The gain/risk ratio flips: 'technologies' is the
project's priority field and it's reliable.

Usage: from the repo ROOT -> python3 extract_skills.py
Incremental resume: only offers absent from previous dumps are processed.
Measured duration: 34.5 s/offer (317 min for 552 offers).

The extraction prompt below stays in French: it's a measured, validated
configuration (model choice + exact wording, three iterations tested), not
just code -- translating it could shift the LLM's actual extraction
behavior without a new measurement.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import duckdb
from ollama import chat

sys.path.insert(0, "exploration")
from schema_extraction import ExtractionOffre

MODEL = "mistral-nemo"
DB_PATH = "data/warehouse.duckdb"
OUTPUT_DIR = Path("data/raw")

PROMPT = """Tu extrais des informations factuelles d'une offre d'emploi française.

Règle générale : n'extrais QUE ce qui est explicitement écrit dans le texte.
N'invente rien. Si une information est absente, retourne null (ou une liste
vide pour les champs de type liste).

Consignes par champ :

technologies : noms propres de produits, langages, logiciels, services.
Exemples valides : Python, SQL, PostgreSQL, Docker, Git, Azure, Databricks.
RÈGLE ABSOLUE : un élément = exactement UN produit.
  "SQL/PostgreSQL" donne deux éléments : "SQL", "PostgreSQL"
  "Azure : Storage, Data Factory" donne trois éléments : "Azure", "Azure Storage", "Azure Data Factory"
Aucun élément ne doit contenir de parenthèse, de virgule ni de barre oblique.
TEST DE DÉCISION, à appliquer à chaque terme avant de l'inclure : peut-on
l'installer, s'y abonner, ou taper exactement ce nom dans un moteur de
recherche pour arriver sur le site d'UN éditeur précis ? Si non, ce n'est
PAS une technologie.
Exemples de termes qui échouent ce test, donc EXCLUS de technologies (ils
vont dans domaines s'ils y ont leur place) : RAG, fine-tuning, streaming,
CI/CD, Data Lake, Lakehouse, RGPD, AI Act, agents autonomes, orchestration
multi-modèles, Machine Learning, algorithmes, gouvernance.
Un terme placé dans 'technologies' ne doit JAMAIS apparaître aussi dans
'domaines' : les deux listes sont mutuellement exclusives.
Liste vide si l'annonce ne nomme aucune technologie : c'est un résultat
normal et attendu pour les annonces de conseil en stratégie, qui décrivent
des missions sans jamais citer d'outil.

domaines : concepts, méthodes, disciplines, pratiques techniques.
Exemples valides : ETL, ELT, Machine Learning, Deep Learning, IA générative,
NLP, vision par ordinateur, gouvernance des données, architecture data,
gestion de projet, agilité, CI/CD, qualité des données, RAG, fine-tuning,
Data Lake, Lakehouse, streaming.
SOIS EXHAUSTIF : parcours le texte en entier et relève CHAQUE concept
technique mentionné, même cité une seule fois, même en passant dans une
énumération. Ne te limite pas aux deux ou trois thèmes principaux de
l'annonce. Une annonce de conseil qui ne nomme aucun produit contient
généralement DE NOMBREUX concepts : c'est normal et attendu.
Un terme placé dans 'technologies' ne doit JAMAIS apparaître aussi dans
'domaines' : les deux listes sont mutuellement exclusives.
N'y mets PAS les produits nommés, ni les secteurs d'activité (aéronautique,
banque, santé), ni les qualités personnelles (rigueur, autonomie, curiosité,
sens du relationnel, gestion des priorités).

niveau_etudes : normalise STRICTEMENT au format "Bac+N", rien d'autre.
  "Bac+5 ou plus en Informatique" donne "Bac+5"
  "BAC + 2" donne "Bac+2"
null si aucun niveau n'est exigé.

annees_experience_min : entier, années.
  "3 ans minimum" donne 3 ; "entre 3 et 5 ans" donne 3
  "jeune diplômé" ou "débutant accepté" donne 0
null si aucune durée chiffrée n'apparaît dans le texte. Ne déduis JAMAIS
une durée d'un niveau de séniorité ("expérimenté", "confirmé", "senior") :
en l'absence de chiffre écrit, la valeur est null.

teletravail : reformule en une expression COURTE, 5 mots maximum.
  "Jusqu'à 10 jours de télétravail par mois" donne "10 jours par mois"
  "Télétravail hybride" donne "hybride"
null si le sujet n'est pas abordé.

anglais_requis : true seulement si l'anglais est explicitement exigé ou mentionné
comme nécessaire. null si le sujet n'est pas abordé (cas le plus fréquent).

salaire_texte : UNIQUEMENT s'il y a un MONTANT CHIFFRÉ en euros.
  "Le salaire est de 54900EUR selon profil" donne "54900 EUR selon profil"
Les primes, participation, intéressement, PERECO ou "salaire attractif" ne sont
PAS des montants. En l'absence de montant chiffré, la valeur DOIT être null,
jamais une phrase expliquant l'absence.

entreprise_nom_texte : le nom de l'entreprise ou du cabinet qui recrute,
mentionné explicitement dans le texte (raison sociale, pas un acronyme de
poste). Distingue BIEN qui parle : si un cabinet dit "nous recrutons pour
notre client", le nom à extraire est celui du CABINET, pas du client (le
client est justement non nommé).
null si aucun nom n'apparaît dans le texte.

client_final_masque : true UNIQUEMENT si le texte dit explicitement que
l'annonceur recrute POUR UNE AUTRE entreprise non nommée ("notre client",
"pour le compte de", "accompagner un grand groupe" en parlant d'un tiers).
false si l'entreprise nommée parle d'ELLE-MÊME, même si elle utilise des
formulations comme "un grand groupe" ou "un acteur majeur" pour se décrire.
Exemple : "Framatome... les avantages d'un grand groupe" -> false, c'est
Framatome qui parle de son propre statut, personne n'est masqué.
Exemple : "CIMPA... accompagner notre client grand industriel Airbus" ->
true, le client (Airbus) est nommé mais CIMPA agit pour son compte.
null si le texte ne permet pas de trancher.

Texte de l'offre :
---
{description}
---"""


def load_already_extracted_ids() -> set[str]:
    """Union of job_offer_id across every previous extraction dump.

    Reads a pattern rather than a frozen filename: that coupling is exactly
    what would have made the 552 July offers rebuild endlessly on the `raw`
    source side (Phase 5 bug). One more dump should enrich the resume,
    never break it.
    """
    ids: set[str] = set()
    for path in sorted(OUTPUT_DIR.glob("extract_skills_*.json")):
        with open(path, encoding="utf-8") as fh:
            dump = json.load(fh)
        ids.update(
            result["job_offer_id"]
            for result in dump.get("resultats", [])
            if result.get("job_offer_id")
        )
    return ids


def write_dump(path: Path, results: list, failures: list, duration: float) -> None:
    """Writes the {metadata, resultats} dump, the structure shared with the
    FT and DINUM dumps.

    Called periodically, not only at the end of the run: a crash at H+3 on a
    4h run shouldn't cost 4 hours. The partial file is read back on the next
    launch by load_already_extracted_ids() -- checkpoint and resume are the
    same mechanism, written once.
    """
    dump = {
        "metadata": {
            "execution_date": datetime.now().isoformat(),
            "model": MODEL,
            "target_population": "fct_job_offer, offers with no prior extraction (incremental resume)",
            "offer_count": len(results),
            "failure_count": len(failures),
            "failed_offers": failures,
            "duration_seconds": round(duration, 1),
            "average_duration_per_offer": round(duration / len(results), 1) if results else None,
        },
        "resultats": results,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(dump, fh, ensure_ascii=False, indent=2)


def load_offers() -> list[tuple[str, str, str]]:
    """Reads fct_job_offer rather than stg_raw__ft_job_offers.

    fct_job_offer is materialized as a table: it can be queried from any
    directory. stg_raw__ft_job_offers is a view, whose relative path to the
    source JSON only resolves from france_data_market/ (known pitfall).
    read_only=True to avoid taking DuckDB's single-writer lock.
    """
    con = duckdb.connect(DB_PATH, read_only=True)
    offers = con.execute("""
        select job_offer_id, job_title, job_description
        from fct_job_offer
        order by job_offer_id
    """).fetchall()
    con.close()

    # Filtered IN PYTHON, never via a SQL `not in`: an IN() with several
    # hundred values crashes the DuckDB optimizer (known bug,
    # version-independent). A set comparison sidesteps the issue.
    already_extracted = load_already_extracted_ids()
    new_offers = [offer for offer in offers if offer[0] not in already_extracted]

    print(f"fct_job_offer        : {len(offers)}")
    print(f"Already extracted    : {len(already_extracted)}")
    print(f"To extract this run  : {len(new_offers)}\n")

    return new_offers


def extract_one_offer(description: str) -> ExtractionOffre:
    """A single LLM call constrained by the schema. temperature=0: no creativity."""
    response = chat(
        model=MODEL,
        messages=[{"role": "user", "content": PROMPT.format(description=description)}],
        format=ExtractionOffre.model_json_schema(),
        options={"temperature": 0},
    )
    return ExtractionOffre.model_validate_json(response.message.content)


def main() -> None:
    offers = load_offers()
    total = len(offers)

    # "Nothing to do" is a normal state for an incremental script, not an
    # error. Returning here also avoids a division by zero when computing
    # the average duration at the end of the dump.
    if total == 0:
        print("Nothing to extract: every offer in fct_job_offer already has a result.")
        return

    print(f"Model            : {MODEL}")
    print(f"Estimated time   : {total * 34.5 / 60:.0f} minutes (34.5 s/offer measured)\n")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    output_path = OUTPUT_DIR / f"extract_skills_{timestamp}.json"

    results = []
    failures = []
    start_time = time.time()

    for i, (offer_id, title, description) in enumerate(offers, 1):
        try:
            extraction = extract_one_offer(description)
            results.append({
                "job_offer_id": offer_id,
                "extraction_status": "ok",
                "error": None,  # always present: heterogeneous keys would
                                # make read_json_auto infer an incomplete
                                # schema (pitfall identified at gate 0)
                **extraction.model_dump(),
            })
        except Exception as err:
            # A failure is a fact to count and trace, not a reason to
            # interrupt a 3h run. The row is kept with a distinct status so
            # the failure rate is measurable downstream, like the DINUM
            # enrichment's match_status.
            failures.append(offer_id)
            results.append({
                "job_offer_id": offer_id,
                "extraction_status": "echec",
                "error": str(err)[:200],
                "technologies": [],
                "domaines": [],
                "niveau_etudes": None,
                "annees_experience_min": None,
                "teletravail": None,
                "anglais_requis": None,
                "salaire_texte": None,
                "entreprise_nom_texte": None,
                "client_final_masque": None,
            })

        # Progress every 10 offers: over a 3h run, a silent terminal doesn't
        # let you tell "it's progressing" from "it's stuck".
        if i % 10 == 0 or i == total:
            elapsed = time.time() - start_time
            remaining = (elapsed / i) * (total - i)
            print(f"[{i:3}/{total}] {elapsed / 60:5.1f} min elapsed | "
                  f"~{remaining / 60:5.1f} min remaining | failures: {len(failures)}")

        # Checkpoint every 25 offers (~14 min). See write_dump().
        if i % 25 == 0:
            write_dump(output_path, results, failures, time.time() - start_time)

    total_duration = time.time() - start_time

    write_dump(output_path, results, failures, total_duration)

    print(f"\n{'=' * 70}")
    print(f"Done in {total_duration / 60:.1f} minutes")
    print(f"Failures  : {len(failures)}/{total}")
    print(f"Dump written: {output_path}")


if __name__ == "__main__":
    main()
