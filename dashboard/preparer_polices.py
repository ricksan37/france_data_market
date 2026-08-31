"""
preparer_polices.py

Fabrique dashboard/fonts/*.woff2 : les trois polices Millimeter Dark,
sous-ensemblees au latin et converties, pretes a etre embarquees en base64
dans le rapport.

POURQUOI EMBARQUER PLUTOT QUE DECLARER. Le rapport declarait des polices
systeme ('Arial Black', -apple-system, 'SF Mono') pour rester un fichier
autonome, consultable hors ligne (decision Session 7). L'intention etait
bonne, la consequence ne l'etait pas : rendu sur une machine sans Arial
Black, les titres de charts perdent leurs accents -- mesure du 31/08, les
titres contiennent bien \\u00c9 dans le HTML mais s'affichent "DEMANDEES".
Un livrable de portfolio ne peut pas dependre des polices installees chez
celui qui l'ouvre. Embarquer en base64 tient les deux exigences a la fois :
autonome ET conforme a l'identite.

POURQUOI UN SCRIPT SEPARE. Il a besoin du reseau et de fonttools, deux
choses absentes du runner CI. Les .woff2 produits sont commites ; la CI se
contente de les lire. A relancer uniquement si l'identite change.

TELECHARGEMENT VIA requests ET NON urllib. urllib s'appuie sur le magasin
de certificats de l'interpreteur ; un Python installe depuis python.org sur
macOS n'en a aucun tant qu'on n'a pas lance Install Certificates.command, et
le script echoue en CERTIFICATE_VERIFY_FAILED. requests embarque son propre
bundle via certifi et fait deja partie des dependances du projet (auth.py,
search.py) : le script devient portable au lieu de dependre de la
configuration de la machine.

Dependances : pip install -r requirements-dev.txt
Lancement   : depuis la racine, avec l'interpreteur du venv EXPLICITE
              (le cache de resolution zsh peut renvoyer le python systeme
              malgre un venv actif, piege Session 6) ->
                  .venv/bin/python3 dashboard/preparer_polices.py
"""

import io
from pathlib import Path

import requests

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools import subset

DOSSIER = Path(__file__).resolve().parent / "fonts"
DEPOT = "https://raw.githubusercontent.com/google/fonts/main/ofl"

# Les trois familles de l'identite Millimeter Dark. Inter et JetBrains Mono
# sont distribuees en polices variables : on en fige une instance par graisse
# reellement utilisee plutot que d'embarquer tout l'axe (856 Ko pour Inter).
SOURCES = [
    ("ArchivoBlack",           f"{DEPOT}/archivoblack/ArchivoBlack-Regular.ttf",      None),
    ("Inter-Regular",          f"{DEPOT}/inter/Inter%5Bopsz%2Cwght%5D.ttf",           400),
    ("Inter-SemiBold",         f"{DEPOT}/inter/Inter%5Bopsz%2Cwght%5D.ttf",           600),
    ("JetBrainsMono-Regular",  f"{DEPOT}/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf",  400),
]

LICENCES = [
    ("ArchivoBlack-OFL.txt",   f"{DEPOT}/archivoblack/OFL.txt"),
    ("Inter-OFL.txt",          f"{DEPOT}/inter/OFL.txt"),
    ("JetBrainsMono-OFL.txt",  f"{DEPOT}/jetbrainsmono/OFL.txt"),
]

# Latin de base, supplement latin-1 (les accents francais), ligatures oe,
# ponctuation typographique et euro. Tout le reste est retire : c'est ce qui
# fait passer Inter de 856 Ko a 12 Ko.
UNICODES = (
    "U+0020-007E,U+00A0-00FF,U+0152-0153,U+02C6,"
    "U+2010-2015,U+2018-201A,U+201C-201E,U+2020-2022,U+2026,U+2030,"
    "U+2039-203A,U+20AC,U+2122"
)


def fabriquer(nom: str, url: str, graisse: int | None) -> int:
    """Telecharge, fige la graisse si police variable, sous-ensemble, ecrit le woff2."""
    reponse = requests.get(url, timeout=60)
    reponse.raise_for_status()
    police = TTFont(io.BytesIO(reponse.content))

    if graisse is not None:
        axes = {a.axisTag for a in police["fvar"].axes}
        reglages = {"wght": graisse}
        if "opsz" in axes:
            reglages["opsz"] = 14  # taille optique pour du texte courant
        police = instancer.instantiateVariableFont(police, reglages)

    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = ["kern", "liga"]
    options.desubroutinize = True
    options.name_IDs = ["*"]  # conserve les metadonnees de licence dans le fichier

    decoupeur = subset.Subsetter(options=options)
    decoupeur.populate(unicodes=subset.parse_unicodes(UNICODES))
    decoupeur.subset(police)

    cible = DOSSIER / f"{nom}.woff2"
    police.flavor = "woff2"
    police.save(cible)
    return cible.stat().st_size


def main() -> None:
    DOSSIER.mkdir(parents=True, exist_ok=True)
    total = 0

    for nom, url, graisse in SOURCES:
        taille = fabriquer(nom, url, graisse)
        total += taille
        print(f"  {nom:24} {taille / 1024:6.1f} Ko")

    # La licence OFL exige que le texte accompagne les fichiers redistribues.
    for nom, url in LICENCES:
        reponse = requests.get(url, timeout=60)
        reponse.raise_for_status()
        (DOSSIER / nom).write_bytes(reponse.content)
    print(f"  {len(LICENCES)} licences OFL ecrites")

    print(f"\nTotal embarque : {total / 1024:.1f} Ko (~{total * 1.34 / 1024:.0f} Ko une fois en base64)")


if __name__ == "__main__":
    main()
