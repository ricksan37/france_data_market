"""
Extraction des compétences depuis le texte des offres — Phase 4 (spec §8).

Réplique le pattern d'ingestion établi en Phase 1 et Phase 3 : script Python
-> dump JSON horodaté dans data/raw/ -> source dbt -> modèle stg_. dbt ne fait
pas d'appels LLM, pas plus qu'il ne fait d'appels HTTP.

MODÈLE RETENU : mistral-nemo (12B), après comparaison mesurée sur un
échantillon de 20 offres contre mistral 7B et qwen3 8B. Critère décisif : seul
Nemo distingue correctement un produit nommé (Azure, Databricks) d'un concept
technique (RAG, CI/CD, Data Lake) — défaut irréductible par prompt sur les
deux modèles 7-8B, testé sur trois formulations successives.

LIMITE CONNUE ET ASSUMÉE : Nemo sous-extrait le champ 'domaines' sur les
annonces de conseil. Mesuré : 4 concepts relevés sur ~8 présents dans le texte
(offre 0388930). Non corrigé : une itération supplémentaire de prompt a produit
un gain marginal sur 'domaines' au prix d'une hallucination sur
annees_experience_min. Le rapport gain/risque s'inverse — 'technologies' est le
champ prioritaire du projet et il est fiable.

Lancement : depuis la RACINE du repo -> python3 extraction_skills.py
Durée attendue : ~3 h pour 552 offres (19 s/offre mesurées sur échantillon).
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

MODELE = "mistral-nemo"
CHEMIN_DB = "data/warehouse.duckdb"
DOSSIER_SORTIE = Path("data/raw")

PROMPT = """Tu extrais des informations factuelles d'une offre d'emploi française.

Règle générale : n'extrais QUE ce qui est explicitement écrit dans le texte.
N'invente rien. Si une information est absente, retourne null (ou une liste
vide pour les champs de type liste).

Consignes par champ :

technologies — noms propres de produits, langages, logiciels, services.
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
Liste vide si l'annonce ne nomme aucune technologie — c'est un résultat
normal et attendu pour les annonces de conseil en stratégie, qui décrivent
des missions sans jamais citer d'outil.

domaines — concepts, méthodes, disciplines, pratiques techniques.
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

niveau_etudes — normalise STRICTEMENT au format "Bac+N", rien d'autre.
  "Bac+5 ou plus en Informatique" donne "Bac+5"
  "BAC + 2" donne "Bac+2"
null si aucun niveau n'est exigé.

annees_experience_min — entier, années.
  "3 ans minimum" donne 3 ; "entre 3 et 5 ans" donne 3
  "jeune diplômé" ou "débutant accepté" donne 0
null si aucune durée chiffrée n'apparaît dans le texte. Ne déduis JAMAIS
une durée d'un niveau de séniorité ("expérimenté", "confirmé", "senior") :
en l'absence de chiffre écrit, la valeur est null.

teletravail — reformule en une expression COURTE, 5 mots maximum.
  "Jusqu'à 10 jours de télétravail par mois" donne "10 jours par mois"
  "Télétravail hybride" donne "hybride"
null si le sujet n'est pas abordé.

anglais_requis — true seulement si l'anglais est explicitement exigé ou mentionné
comme nécessaire. null si le sujet n'est pas abordé (cas le plus fréquent).

salaire_texte — UNIQUEMENT s'il y a un MONTANT CHIFFRÉ en euros.
  "Le salaire est de 54900EUR selon profil" donne "54900 EUR selon profil"
Les primes, participation, intéressement, PERECO ou "salaire attractif" ne sont
PAS des montants. En l'absence de montant chiffré, la valeur DOIT être null —
jamais une phrase expliquant l'absence.

Texte de l'offre :
---
{description}
---"""


def charger_offres() -> list[tuple[str, str, str]]:
    """Lit fct_offre plutôt que stg_ft_offres.

    fct_offre est matérialisée en table : elle s'interroge depuis n'importe
    quel répertoire. stg_ft_offres est une vue, dont le chemin relatif vers le
    JSON source ne se résout que depuis observatoire/ (piège S5).
    read_only=True pour ne pas prendre le verrou mono-écrivain DuckDB.
    """
    con = duckdb.connect(CHEMIN_DB, read_only=True)
    offres = con.execute("""
        select offre_id, intitule, description
        from fct_offre
        order by offre_id
    """).fetchall()
    con.close()
    return offres


def extraire_une_offre(description: str) -> ExtractionOffre:
    """Un appel LLM contraint par le schéma. temperature=0 : pas de créativité."""
    reponse = chat(
        model=MODELE,
        messages=[{"role": "user", "content": PROMPT.format(description=description)}],
        format=ExtractionOffre.model_json_schema(),
        options={"temperature": 0},
    )
    return ExtractionOffre.model_validate_json(reponse.message.content)


def main() -> None:
    offres = charger_offres()
    total = len(offres)
    print(f"Offres a traiter : {total}")
    print(f"Modele           : {MODELE}")
    print(f"Duree estimee    : {total * 19 / 60:.0f} minutes\n")

    resultats = []
    echecs = []
    debut_total = time.time()

    for i, (offre_id, intitule, description) in enumerate(offres, 1):
        try:
            extraction = extraire_une_offre(description)
            resultats.append({
                "offre_id": offre_id,
                "statut_extraction": "ok",
                "erreur": None,  # toujours présente : des clés hétérogènes
                                 # feraient inférer un schéma incomplet à
                                 # read_json_auto (piège identifié au palier 0)
                **extraction.model_dump(),
            })
        except Exception as err:
            # Un échec est un fait à compter et à tracer, pas une raison
            # d'interrompre 3 h de traitement. La ligne est conservée avec
            # un statut distinct pour que le taux d'échec soit mesurable en
            # aval, comme le statut_matching de la Phase 3.
            echecs.append(offre_id)
            resultats.append({
                "offre_id": offre_id,
                "statut_extraction": "echec",
                "erreur": str(err)[:200],
                "technologies": [],
                "domaines": [],
                "niveau_etudes": None,
                "annees_experience_min": None,
                "teletravail": None,
                "anglais_requis": None,
                "salaire_texte": None,
            })

        # Progression toutes les 10 offres : sur 3 h de traitement, un
        # terminal muet ne permet pas de distinguer "ça avance" de "c'est figé".
        if i % 10 == 0 or i == total:
            ecoule = time.time() - debut_total
            reste = (ecoule / i) * (total - i)
            print(f"[{i:3}/{total}] {ecoule / 60:5.1f} min ecoulees | "
                  f"~{reste / 60:5.1f} min restantes | echecs : {len(echecs)}")

    duree_totale = time.time() - debut_total

    horodatage = datetime.now().strftime("%Y-%m-%d_%H%M")
    chemin_sortie = DOSSIER_SORTIE / f"extraction_skills_{horodatage}.json"

    # Structure {metadata, resultats} identique aux dumps France Travail et
    # DINUM : traçabilité de l'exécution, pas seulement des données.
    dump = {
        "metadata": {
            "date_execution": datetime.now().isoformat(),
            "modele": MODELE,
            "population_cible": "fct_offre (toutes les offres)",
            "nb_offres": total,
            "nb_echecs": len(echecs),
            "offres_en_echec": echecs,
            "duree_secondes": round(duree_totale, 1),
            "duree_moyenne_par_offre": round(duree_totale / total, 1),
        },
        "resultats": resultats,
    }

    with open(chemin_sortie, "w", encoding="utf-8") as fh:
        json.dump(dump, fh, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 70}")
    print(f"Termine en {duree_totale / 60:.1f} minutes")
    print(f"Echecs     : {len(echecs)}/{total}")
    print(f"Dump ecrit : {chemin_sortie}")


if __name__ == "__main__":
    main()