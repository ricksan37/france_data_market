# check_rome.py
"""
Script d'exploration : quels codes ROME se cachent derrière un mot-clé ?

Le miroir de check_codeROME.py. Ici on part d'un mot-clé (ex: "data architect")
et on compte la répartition des codes ROME parmi les offres qui matchent. Ça
répond à la question : "ce mot-clé tombe-t-il dans un code ROME unique et
propre, ou est-il éparpillé sur plein de codes ?".

C'est ce comptage qui a montré que certains intitulés data n'ont pas de code
ROME dédié et sont dispersés dans des métiers fourre-tout, d'où le recours
au filtrage par motsCles pour ces cas (stratégie hybride, cf. pull_complet.py).

Script jetable, gardé dans exploration/ pour tracer la démarche.
"""

from search import search_offres
from collections import Counter


def check_rome(mots_cles: str) -> None:
    """
    Affiche la répartition (code ROME, libellé) des offres d'un mot-clé.

    mots_cles : str passé à l'API en paramètre motsCles. Un seul appel
    (search_offres, non paginé) : l'échantillon de la 1re page suffit à
    voir la dispersion. Trie du plus fréquent au moins fréquent.
    """
    # search_offres attend un dict de paramètres API : on enveloppe le mot-clé.
    data = search_offres({"motsCles": mots_cles})
    resultats = data.get("resultats", [])

    # Compte les couples (code, libellé) : une entrée = un code ROME distinct.
    counts = Counter(
        (o.get("romeCode"), o.get("romeLibelle")) for o in resultats
    )

    # Alignement à droite du compte (>3) pour une lecture en colonnes propre.
    for (code, libelle), n in counts.most_common():
        print(f"{n:>3}  {code}  {libelle}")


if __name__ == "__main__":
    check_rome("data architect")  # cas testé : mot-clé dispersé sur plusieurs ROME
