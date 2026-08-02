"""
Premier appel d'extraction réel : une offre, un modèle, le schéma complet.

DÉCOUVERTE (S6) : les `description` des Field Pydantic ne parviennent PAS au
modèle. Ollama compile le JSON Schema en grammaire, laquelle n'encode que la
structure (clés, types, imbrication) ; les descriptions sont écartées. Toute
consigne de SENS doit donc vivre dans le prompt. Les descriptions du schéma
restent en place comme documentation du code, mais elles ne pilotent rien.

ATTENTION : stg_ft_offres est une vue -> lancement obligatoire depuis
observatoire/, sinon son chemin relatif vers le JSON ne se résout pas.

Lancement : depuis observatoire/  ->  python3 ../exploration/test_extraction_une_offre.py
"""

import sys
import time

import duckdb
from ollama import chat

sys.path.insert(0, "../exploration")
from schema_extraction import ExtractionOffre

MODELE = "mistral-nemo"
CHEMIN_DB = "../data/warehouse.duckdb"

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
multi-modèles, Machine Learning, algorithmes, gouvernance. ID/CD est une
pratique, RGPD/AI Act sont des réglementations, Data Lake/Lakehouse sont des
architectures — aucun n'a d'éditeur unique.
Un terme placé dans 'technologies' ne doit JAMAIS apparaître aussi dans
'domaines' : les deux listes sont mutuellement exclusives.
Liste vide si l'annonce ne nomme aucune technologie — c'est un résultat
normal et attendu pour les annonces de conseil en stratégie, qui décrivent
des missions sans jamais citer d'outil (cabinets comme EY, McKinsey...).

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
null si aucune durée chiffrée.

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

entreprise_nom_texte — le nom de l'entreprise ou du cabinet qui recrute,
mentionné explicitement dans le texte (raison sociale, pas un acronyme de
poste). Distingue BIEN qui parle : si un cabinet dit "nous recrutons pour
notre client", le nom à extraire est celui du CABINET, pas du client (le
client est justement non nommé).
null si aucun nom n'apparaît dans le texte.

client_final_masque — true UNIQUEMENT si le texte dit explicitement que
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


def main() -> None:
    # read_only=True : ne jamais verrouiller la base pendant la lecture
    # (piège du verrou mono-écrivain DuckDB, S4).
    con = duckdb.connect(CHEMIN_DB, read_only=True)
    offre_id, intitule, description = con.execute("""
        select offre_id, intitule, description
        from stg_ft_offres
        where offre_id = '0388930'
    """).fetchone()
    con.close()

    print(f"Offre : {offre_id} — {intitule}")
    print(f"Longueur description : {len(description)} caracteres\n")

    debut = time.time()
    kwargs = {"think": False} if "qwen" in MODELE else {}
    reponse = chat(
        model=MODELE,
        messages=[{"role": "user", "content": PROMPT.format(description=description)}],
        format=ExtractionOffre.model_json_schema(),
        options={"temperature": 0},
        **kwargs,
    )
    duree = time.time() - debut

    print(f"--- Duree de l'appel : {duree:.1f} s ---\n")

    extraction = ExtractionOffre.model_validate_json(reponse.message.content)

    print(f"technologies ({len(extraction.technologies)}) : {extraction.technologies}")
    print(f"domaines ({len(extraction.domaines)}) : {extraction.domaines}")
    print(f"niveau_etudes           : {extraction.niveau_etudes}")
    print(f"annees_experience_min   : {extraction.annees_experience_min}")
    print(f"teletravail             : {extraction.teletravail}")
    print(f"anglais_requis          : {extraction.anglais_requis}")
    print(f"salaire_texte           : {extraction.salaire_texte}")


if __name__ == "__main__":
    main()