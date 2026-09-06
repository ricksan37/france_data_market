"""
Extraction des compétences depuis le texte des offres, Phase 4 (spec §8).

Réplique le pattern d'ingestion établi en Phase 1 et Phase 3 : script Python
-> dump JSON horodaté dans data/raw/ -> source dbt -> modèle stg_. dbt ne fait
pas d'appels LLM, pas plus qu'il ne fait d'appels HTTP.

MODÈLE RETENU : mistral-nemo (12B), après comparaison mesurée sur un
échantillon de 20 offres contre mistral 7B et qwen3 8B. Critère décisif : seul
Nemo distingue correctement un produit nommé (Azure, Databricks) d'un concept
technique (RAG, CI/CD, Data Lake) : défaut irréductible par prompt sur les
deux modèles 7-8B, testé sur trois formulations successives.

LIMITE CONNUE ET ASSUMÉE : Nemo sous-extrait le champ 'domaines' sur les
annonces de conseil. Mesuré : 4 concepts relevés sur ~8 présents dans le texte
(offre 0388930). Non corrigé : une itération supplémentaire de prompt a produit
un gain marginal sur 'domaines' au prix d'une hallucination sur
annees_experience_min. Le rapport gain/risque s'inverse : 'technologies' est le
champ prioritaire du projet et il est fiable.

Lancement : depuis la RACINE du repo -> python3 extraction_skills.py
Reprise incrémentale : seules les offres absentes des dumps précédents sont
traitées. Durée mesurée : 34,5 s/offre (317 min pour 552 offres).
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


def charger_ids_deja_extraits() -> set[str]:
    """Union des offre_id de tous les dumps d'extraction precedents.

    Lit un motif et non un nom fige : c'est ce couplage qui aurait fait
    reconstruire indefiniment les 552 offres de juillet cote source `raw`
    (bug Phase 5). Un dump de plus doit enrichir la reprise, jamais la casser.
    """
    ids: set[str] = set()
    for chemin in sorted(DOSSIER_SORTIE.glob("extraction_skills_*.json")):
        with open(chemin, encoding="utf-8") as fh:
            dump = json.load(fh)
        ids.update(
            resultat["offre_id"]
            for resultat in dump.get("resultats", [])
            if resultat.get("offre_id")
        )
    return ids


def ecrire_dump(chemin: Path, resultats: list, echecs: list, duree: float) -> None:
    """Ecrit le dump {metadata, resultats}, structure commune aux dumps FT et DINUM.

    Appelee periodiquement et pas seulement en fin de run : un plantage a H+3
    sur 4 h de traitement ne doit pas couter 4 h. Le fichier partiel est relu
    au lancement suivant par charger_ids_deja_extraits() -- checkpoint et
    reprise sont le meme mecanisme, ecrit une fois.
    """
    dump = {
        "metadata": {
            "date_execution": datetime.now().isoformat(),
            "modele": MODELE,
            "population_cible": "fct_offre, offres sans extraction anterieure (reprise incrementale)",
            "nb_offres": len(resultats),
            "nb_echecs": len(echecs),
            "offres_en_echec": echecs,
            "duree_secondes": round(duree, 1),
            "duree_moyenne_par_offre": round(duree / len(resultats), 1) if resultats else None,
        },
        "resultats": resultats,
    }
    with open(chemin, "w", encoding="utf-8") as fh:
        json.dump(dump, fh, ensure_ascii=False, indent=2)


def charger_offres() -> list[tuple[str, str, str]]:
    """Lit fct_offre plutôt que stg_ft_offres.

    fct_offre est matérialisée en table : elle s'interroge depuis n'importe
    quel répertoire. stg_ft_offres est une vue, dont le chemin relatif vers le
    JSON source ne se résout que depuis observatoire/ (piège connu).
    read_only=True pour ne pas prendre le verrou mono-écrivain DuckDB.
    """
    con = duckdb.connect(CHEMIN_DB, read_only=True)
    offres = con.execute("""
        select offre_id, intitule, description
        from fct_offre
        order by offre_id
    """).fetchall()
    con.close()

    # Filtre EN PYTHON, jamais par un `not in` SQL : un IN() a plusieurs
    # centaines de valeurs fait planter l'optimiseur DuckDB (bug connu,
    # version-independant). Une comparaison de sets contourne le sujet.
    deja_extraites = charger_ids_deja_extraits()
    nouvelles = [offre for offre in offres if offre[0] not in deja_extraites]

    print(f"fct_offre            : {len(offres)}")
    print(f"Deja extraites       : {len(deja_extraites)}")
    print(f"A extraire ce run    : {len(nouvelles)}\n")

    return nouvelles


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

    # "Rien a faire" est un etat normal d'un script incremental, pas une
    # erreur. Sortir ici evite en prime la division par zero du calcul de
    # duree moyenne en fin de dump.
    if total == 0:
        print("Rien a extraire : toutes les offres de fct_offre ont un resultat.")
        return

    print(f"Modele           : {MODELE}")
    print(f"Duree estimee    : {total * 34.5 / 60:.0f} minutes (34,5 s/offre mesurees)\n")

    horodatage = datetime.now().strftime("%Y-%m-%d_%H%M")
    chemin_sortie = DOSSIER_SORTIE / f"extraction_skills_{horodatage}.json"

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
                "entreprise_nom_texte": None,
                "client_final_masque": None,
            })

        # Progression toutes les 10 offres : sur 3 h de traitement, un
        # terminal muet ne permet pas de distinguer "ça avance" de "c'est figé".
        if i % 10 == 0 or i == total:
            ecoule = time.time() - debut_total
            reste = (ecoule / i) * (total - i)
            print(f"[{i:3}/{total}] {ecoule / 60:5.1f} min ecoulees | "
                  f"~{reste / 60:5.1f} min restantes | echecs : {len(echecs)}")

        # Checkpoint toutes les 25 offres (~14 min). Voir ecrire_dump().
        if i % 25 == 0:
            ecrire_dump(chemin_sortie, resultats, echecs, time.time() - debut_total)

    duree_totale = time.time() - debut_total

    ecrire_dump(chemin_sortie, resultats, echecs, duree_totale)

    print(f"\n{'=' * 70}")
    print(f"Termine en {duree_totale / 60:.1f} minutes")
    print(f"Echecs     : {len(echecs)}/{total}")
    print(f"Dump ecrit : {chemin_sortie}")


if __name__ == "__main__":
    main()