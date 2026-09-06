# get_referentiel.py
"""
Script d'exploration : récupérer un référentiel de l'API et pré-filtrer les
appellations liées à la data.

L'API expose des référentiels (communes, appellations, etc.). Ici on récupère
le référentiel "appellations" (la liste officielle des intitulés de métiers)
et on le tamise sur quelques mots-clés data pour repérer, en amont, tous les
libellés susceptibles de nous intéresser. Ça sert à cadrer le périmètre avant
d'interroger les offres.

Script jetable, gardé dans exploration/ pour tracer la démarche.
"""

from auth import get_access_token
import requests

# URL paramétrable par type de référentiel ({type} formaté à l'appel).
REFERENTIEL_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/referentiel/{type}"


def get_referentiel(type_referentiel: str) -> list[dict] | None:
    """
    Récupère un référentiel complet de l'API.

    type_referentiel : str, ex. "appellations". Retourne le JSON décodé
    (liste de dicts) en cas de succès, ou None si l'appel échoue, auquel
    cas le corps de la réponse est affiché pour diagnostic.
    """
    token, _ = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = REFERENTIEL_URL.format(type=type_referentiel)

    response = requests.get(url, headers=headers)
    print(f"Statut HTTP : {response.status_code}")

    if response.status_code != 200:
        print(response.text)  # utile pour voir le message d'erreur exact
        return None

    return response.json()


if __name__ == "__main__":
    appellations = get_referentiel("appellations")

    if appellations:
        print(f"Total appellations dans le référentiel : {len(appellations)}")

        # Pré-filtre : on ne garde que les libellés contenant un de ces mots.
        mots_cles = ["data", "analytic", "décisionnel", "business intelligence"]
        matches = [
            a for a in appellations
            if any(mot in a["libelle"].lower() for mot in mots_cles)
        ]
        matches.sort(key=lambda a: a["libelle"])  # tri alphabétique pour la lecture

        print(f"\n{len(matches)} appellations pré-filtrées :\n")
        for a in matches:
            print(f"  {a['code']:>10}  {a['libelle']}")
