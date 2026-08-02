"""
Schéma d'extraction des offres — Phase 4 (spec §8.1, §8.2).

Contrat central : TOUS les champs sont obligatoires, aucun n'a de valeur par
défaut. Un champ optionnel permettrait au modèle de l'omettre, rendant
indistinguables "l'annonce n'en parle pas" et "le modèle a raté". Ici, le
modèle DOIT produire une valeur ; `null` devient donc un fait mesurable
(information absente de la source) et non un échec silencieux.

Listes vs scalaires : les listes sont `list[str]` sans None. Une liste vide
exprime déjà l'absence sans ambiguïté ; ajouter None créerait deux encodages
de la même information. Les scalaires n'ont pas d'équivalent vide, d'où le
`| None`.

Ce fichier ne contient QUE le schéma, aucun appel LLM — les deux inconnues
("le schéma est-il bon ?" et "l'appel fonctionne-t-il ?") sont isolées.
"""

from pydantic import BaseModel, Field


class ExtractionOffre(BaseModel):
    """Champs extraits du texte libre d'une offre d'emploi data."""

    technologies: list[str] = Field(
        description=(
            "Noms propres de produits, langages, logiciels ou services nommés "
            "explicitement dans l'annonce. Exemples : Python, SQL, Docker, Git, "
            "Azure, AWS, Power BI, SAP, Databricks, PostgreSQL, Spark. "
            "RÈGLE ABSOLUE : un élément de la liste = exactement UN produit. "
            "Si le texte écrit 'SQL/PostgreSQL', produire deux éléments : "
            "'SQL' et 'PostgreSQL'. Si le texte écrit 'Azure : Storage, "
            "Data Factory, Databricks', produire quatre éléments : 'Azure', "
            "'Azure Storage', 'Azure Data Factory', 'Databricks'. "
            "Ne jamais produire un élément contenant une parenthèse, une "
            "virgule ou une barre oblique. "
            "Un élément n'entre ici que s'il désigne un produit identifiable "
            "ayant un éditeur ou une communauté qui le maintient. "
            "Ne PAS inclure les concepts généraux (ETL, Machine Learning, "
            "gouvernance) : ils vont dans 'domaines'. "
            "Liste vide si l'annonce ne nomme aucune technologie."
        )
    )

    domaines: list[str] = Field(
        description=(
            "Concepts, méthodes, disciplines ou pratiques mentionnés, sans "
            "être des produits nommés. Exemples : ETL, Machine Learning, "
            "Deep Learning, gouvernance des données, architecture data, "
            "gestion de projet, agilité, CI/CD, qualité des données. "
            "Ne PAS inclure les produits nommés : ils vont dans 'technologies'. "
            "Liste vide si l'annonce n'en mentionne aucun."
        )
    )

    niveau_etudes: str | None = Field(
        description=(
            "Niveau de diplôme demandé, normalisé au format 'Bac+N' "
            "(exemples : 'Bac+5', 'Bac+3', 'Bac+2'). "
            "null si l'annonce n'exige aucun niveau explicite."
        )
    )

    annees_experience_min: int | None = Field(
        description=(
            "Nombre minimal d'années d'expérience exigé, en années entières. "
            "'3 ans minimum' donne 3 ; 'entre 3 et 5 ans' donne 3. "
            "null si aucune durée chiffrée n'est mentionnée. "
            "Attention : 'jeune diplômé' ou 'débutant accepté' donne 0, pas null."
        )
    )

    teletravail: str | None = Field(
        description=(
            "Modalité de télétravail telle qu'énoncée dans l'annonce, en une "
            "formulation courte reprenant les termes du texte. Exemples : "
            "'10 jours par mois', 'hybride', 'occasionnel', '100% présentiel'. "
            "null si l'annonce n'aborde pas le sujet."
        )
    )

    anglais_requis: bool | None = Field(
        description=(
            "true si l'annonce exige ou mentionne explicitement la maîtrise de "
            "l'anglais. false si elle précise explicitement qu'il n'est pas "
            "requis. null si le sujet n'est pas abordé — cas le plus fréquent."
        )
    )

    salaire_texte: str | None = Field(
        description=(
            "Toute mention de rémunération chiffrée trouvée dans le corps du "
            "texte, recopiée telle quelle. Exemples : '54900 EUR selon profil', "
            "'entre 45 et 55K€'. Ne PAS inventer ni estimer. "
            "null si aucun montant n'apparaît."
        )
    )

    entreprise_nom_texte: str | None = Field(
        description=(
            "Nom de l'entreprise ou du cabinet qui recrute/publie l'annonce, "
            "tel qu'il apparaît explicitement dans le texte. Utile quand le nom "
            "structuré de l'offre est vide mais qu'un nom figure dans le corps "
            "du texte (ex: 'Rejoignez CIMPA...'). "
            "null si aucun nom d'entreprise n'est mentionné dans le texte."
        )
    )

    client_final_masque: bool | None = Field(
        description=(
            "true si le texte indique explicitement que l'entreprise qui publie "
            "l'annonce agit pour le compte d'un client final non nommé (formulations "
            "comme 'notre client', 'pour le compte de notre client', 'un grand groupe' "
            "en parlant d'une tierce entreprise cliente). "
            "false si l'entreprise nommée dans entreprise_nom_texte EST l'employeur "
            "direct (elle parle d'elle-même, même en utilisant 'un grand groupe' "
            "pour se décrire elle-même). "
            "null si le texte ne permet pas de trancher."
        )
    )