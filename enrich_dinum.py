"""
Enrichissement entreprise via l'API Recherche d'entreprises (DINUM).
Phase 3, spec FR-014 / FR-015.

Enrichit les offres EMPLOYEUR_DIRECT avec SIREN, NAF, effectif et date de
création, en résolvant le nom d'entreprise saisi par l'employeur vers une
entité légale du répertoire SIRENE.

STRATÉGIE DE MATCHING : construite par paliers mesurés
(19,2% -> 80,3% de taux de matching) :

  Clé géographique : code INSEE commune, PAS le code postal.
    Rouvre §7.5 de la spec, qui prévoyait le code postal. Justification
    mesurée sur les 213 offres cibles : code postal renseigné 166/213,
    code INSEE 198/213 (sur-ensemble strict). Le code INSEE a en outre
    une relation 1:1 avec la commune (§4.1), contrairement au code postal.

  Cascade géographique : commune -> département -> national.
    Le siège social est souvent hors de la commune de l'offre (universités,
    banques régionales, groupes nationaux).

  Comparaison de noms, du plus strict au plus souple :
    1. nom exact, sur variantes (DINUM concatène raison sociale ET
       enseignes/sigles entre parenthèses)
    2. préfixe sur frontière de mot (troncature côté France Travail,
       ou mot ajouté par l'employeur)
    3. inclusion de mots (mot inséré au milieu de la raison sociale)

  Le NAF sert UNIQUEMENT de disambiguant entre candidats déjà retenus par
  le nom. La voie "NAF seul" a été supprimée après audit : 2 matchs sur 172,
  dont 2 douteux. Règle retenue : le nom doit toujours corroborer.

  Consolidation groupe sur homonymes : on retient l'entité au plus grand
  nombre d'établissements. Aligné sur l'objectif analytique du projet
  (caractériser le TYPE de structure qui recrute) : une offre de KEOLIS SUD
  LORRAINE relève bien d'un grand groupe de transport.

LIMITES CONNUES ET ASSUMÉES :
  - "EY" (28 offres, 13%) : sigle commercial absent de SIRENE, et 5+ entités
    juridiques du groupe sans critère de départage. Non matché volontairement.
  - Libellés de service interne ("FONCTIONS SUPPORTS", "751163-DIR STRATEGIE
    INNOVATION ET TRANSFO", "BNP Paribas Mission Handicap") : ce ne sont pas
    des noms d'entreprise, aucune règle ne peut les rattacher correctement.
    Toute règle assez souple pour leur trouver un candidat trouvera un
    MAUVAIS candidat (un CSE, une association satellite). 2 faux positifs
    résiduels mesurés sur 171 matchs. Non filtrés en amont : le critère
    aurait reposé sur une liste de mots-clés construite sur 5 exemples.
  - Consolidation groupe (27 matchs, 16%) : rattache à tort les homonymes
    sans lien capitalistique. Statut distinct pour filtrer en aval.
  - 14 offres (6,6%) non résolues : nom commercial ou libellé interne absent
    du répertoire SIRENE.

USAGE : à lancer depuis la RACINE du projet.
    python3 enrichissement_dinum.py
"""

import duckdb
import requests
import time
import re
import json
import unicodedata
from datetime import datetime

URL_DINUM = "https://recherche-entreprises.api.gouv.fr/search"
CHEMIN_BASE = "data/warehouse.duckdb"
DOSSIER_SORTIE = "data/raw"

# Rate limit DINUM : 7 req/s par IP, HTTP 429 au-delà (spec §7.5)
DELAI_ENTRE_APPELS = 1 / 7

MOTS_VIDES = {"DE", "LA", "LE", "DU", "DES", "ET", "D", "L"}

# Formes juridiques accolées à la raison sociale dans SIRENE, quasi jamais
# écrites par l'employeur dans l'offre (ex. "Keolis" vs "KEOLIS SA").
FORMES_JURIDIQUES = {
    "SA", "SAS", "SASU", "SARL", "EURL", "SNC", "SCS", "SCA",
    "SE", "SCOP", "SCIC", "GIE", "GEIE", "EARL", "SCI", "SEM",
    "SELARL", "SELAS", "SPRL", "GMBH", "LTD", "BV", "NV", "AG", "SPA",
}

# Sigles connus sans correspondance exploitable dans SIRENE.
# Documenté plutôt que contourné : voir LIMITES CONNUES ci-dessus.
SIGLES_NON_MATCHABLES = {"EY"}


# ─────────────────────────────────────────────────────────────
# Normalisation et comparaison de noms
# ─────────────────────────────────────────────────────────────

def normaliser_nom(nom):
    """
    Neutralise ce qui varie entre le nom saisi par l'employeur et la raison
    sociale SIRENE : casse, accents, ponctuation, mots vides, forme juridique.

    Les accents sont critiques : SIRENE stocke sans accents ("DEFI RH",
    "CREDIT AGRICOLE ASSURANCES") alors que l'offre les conserve.

    Garde-fou : on ne retire mots vides et formes juridiques que s'il reste
    au moins un mot. Certaines entreprises s'appellent littéralement "LTd" ;
    les retirer viderait le nom et rendrait toute comparaison impossible.
    """
    nom = nom.strip().upper()

    nom = unicodedata.normalize("NFD", nom)
    nom = "".join(c for c in nom if unicodedata.category(c) != "Mn")

    nom = re.sub(r"[.,'\-&]", " ", nom)

    mots = nom.split()
    mots_filtres = [m for m in mots
                    if m not in MOTS_VIDES and m not in FORMES_JURIDIQUES]

    return " ".join(mots_filtres) if mots_filtres else " ".join(mots)


def variantes_nom(nom_complet):
    """
    DINUM concatène dans nom_complet la raison sociale ET les enseignes ou
    sigles entre parenthèses : "LEIHIA (LEIHIA) (LEIHIA)", "AGENCE FRANCAISE
    DE DEVELOPPEMENT (AFD)". Comparer la chaîne entière échoue donc sur des
    correspondances parfaites.

    Retourne toutes les formes normalisées comparables : chaîne entière,
    raison sociale seule, et chaque contenu de parenthèses isolément.
    """
    formes = {normaliser_nom(nom_complet)}
    formes.add(normaliser_nom(re.sub(r"\([^)]*\)", " ", nom_complet)))
    for contenu in re.findall(r"\(([^)]*)\)", nom_complet):
        for morceau in contenu.split(","):
            forme = normaliser_nom(morceau)
            if forme:
                formes.add(forme)
    return {f for f in formes if f}


def est_prefixe_sur_mot(court, long):
    """
    Vrai si `court` est un préfixe de `long` s'arrêtant sur un mot entier.

    "STEP UP" est préfixe de "STEP UP LILLE" (suivi d'un espace).
    "FED" n'est PAS préfixe de "FEDERATION SPORTIVE" (coupe en plein mot).

    Remplace un garde-fou arbitraire sur la longueur : plus sûr, car il
    devient impossible de matcher sur une troncature de mot.
    """
    if not court or not long:
        return False
    if court == long:
        return True
    return long.startswith(court + " ")


def mots_inclus(nom_court, nom_long):
    """
    Vrai si TOUS les mots de `nom_court` sont présents dans `nom_long`.

    Gère les mots insérés au milieu, que le préfixe ne peut pas attraper :
    "CAISSE EPARGNE LANGUEDOC ROUSSILLON" est inclus dans
    "CAISSE EPARGNE PREVOYANCE LANGUEDOC ROUSSILLON".

    Deux garde-fous :
    - au moins 2 mots, pour éviter qu'un nom d'un seul mot générique soit
      inclus dans des dizaines de candidats ;
    - le candidat ne doit pas faire plus du double de mots. Sans cette borne,
      un libellé de service interne comme "FONCTIONS SUPPORTS" se rattachait
      à "AIDE AUX FONCTIONS SUPPORTS DES ENTREPRISES" : inclusion vraie au
      sens strict, mais entité sans rapport. Un écart de cette ampleur signale
      qu'on a attrapé une entité satellite, pas l'employeur.
    """
    mots_court = set(nom_court.split())
    if len(mots_court) < 2:
        return False

    mots_long = set(nom_long.split())
    if not mots_court.issubset(mots_long):
        return False

    return len(mots_long) <= 2 * len(mots_court)


# ─────────────────────────────────────────────────────────────
# Appels API
# ─────────────────────────────────────────────────────────────

def departement_depuis_commune(code_commune):
    """
    Code département depuis le code INSEE commune.
    Cas DOM : codes en 97x / 98x -> département sur 3 chiffres.
    """
    if not code_commune:
        return None
    if code_commune.startswith("97") or code_commune.startswith("98"):
        return code_commune[:3]
    return code_commune[:2]


def chercher(nom, params_geo):
    """Un appel API avec un jeu de paramètres géographiques donné."""
    params = {"q": nom, **params_geo}
    resp = requests.get(URL_DINUM, params=params)
    resp.raise_for_status()
    time.sleep(DELAI_ENTRE_APPELS)
    return resp.json().get("results", [])


# ─────────────────────────────────────────────────────────────
# Sélection du candidat
# ─────────────────────────────────────────────────────────────

def consolider_groupe(candidats):
    """
    Départage des homonymes par nombre d'établissements.

    Objectif analytique du projet = caractériser le TYPE de structure qui
    recrute (secteur, taille, âge). Rattacher une offre d'une filiale
    régionale à sa maison mère est donc le comportement souhaité, pas une
    approximation regrettable.

    Angle mort assumé : les homonymes SANS lien capitalistique sont
    rattachés à tort -> statut distinct pour mesurer et filtrer en aval.
    """
    avec_etabs = [r for r in candidats if r.get("nombre_etablissements") is not None]
    if not avec_etabs:
        return None
    return max(avec_etabs, key=lambda r: r.get("nombre_etablissements", 0))


def _departager(candidats, code_naf_offre, statut_naf, statut_groupe, autoriser_naf):
    """
    Départage un ensemble de candidats déjà retenus par le nom.
    Facteur commun aux trois modes de correspondance.

    `autoriser_naf` est False au niveau national : sans ancrage géographique,
    un NAF rapprocherait des entreprises du même secteur situées n'importe où.
    """
    if len(candidats) == 1:
        return (statut_naf.replace("_puis_naf", ""), candidats[0])

    if autoriser_naf and code_naf_offre:
        par_naf = [r for r in candidats
                   if r.get("activite_principale") == code_naf_offre]
        if len(par_naf) == 1:
            return (statut_naf, par_naf[0])
        if len(par_naf) > 1:
            candidats = par_naf

    principal = consolider_groupe(candidats)
    if principal:
        return (statut_groupe, principal)
    return None


def selectionner_nom_exact(nom_offre, code_naf_offre, candidats_actifs, autoriser_naf=True):
    """
    PASSE 1 : correspondance exacte du nom uniquement.

    Exécutée sur toute la cascade géographique AVANT toute règle souple :
    un nom exact au niveau national vaut mieux qu'une correspondance
    approximative dans la bonne commune.

    Contre-exemple qui a motivé cette séparation : "UNIVERSITE PARIS-SACLAY"
    matchait par inclusion de mots avec "ASSOCIATION DES ETUDIANTS ... DE
    L'UNIVERSITE PARIS-SACLAY" dans la bonne commune, ce qui court-circuitait
    la découverte de l'université elle-même au niveau département.
    """
    if not candidats_actifs:
        return None

    nom_cible = normaliser_nom(nom_offre)
    par_nom = [r for r in candidats_actifs
               if nom_cible in variantes_nom(r.get("nom_complet", ""))]

    if not par_nom:
        return None

    return _departager(par_nom, code_naf_offre,
                       "match_nom_puis_naf", "match_consolide_groupe",
                       autoriser_naf)


def selectionner_souple(nom_offre, code_naf_offre, candidats_actifs, autoriser_naf=True):
    """
    PASSE 2 : correspondances assouplies, dans l'ordre de fiabilité
    décroissante : préfixe sur frontière de mot, puis inclusion de mots.

    N'est tentée qu'après échec de la passe exacte sur TOUS les niveaux
    géographiques.
    """
    if not candidats_actifs:
        return None

    nom_cible = normaliser_nom(nom_offre)

    par_prefixe = [
        r for r in candidats_actifs
        if any(est_prefixe_sur_mot(nom_cible, v) or est_prefixe_sur_mot(v, nom_cible)
               for v in variantes_nom(r.get("nom_complet", "")))
    ]
    if par_prefixe:
        issue = _departager(par_prefixe, code_naf_offre,
                            "match_prefixe_puis_naf", "match_consolide_groupe_prefixe",
                            autoriser_naf)
        if issue:
            return (issue[0].replace("match_prefixe", "match_nom_prefixe"), issue[1])

    par_inclusion = [
        r for r in candidats_actifs
        if any(mots_inclus(nom_cible, v)
               for v in variantes_nom(r.get("nom_complet", "")))
    ]
    if par_inclusion:
        return _departager(par_inclusion, code_naf_offre,
                           "match_mots_inclus_puis_naf",
                           "match_consolide_groupe_inclusion",
                           autoriser_naf)

    return None


def resoudre_entreprise(nom, commune, code_naf):
    """
    Deux passes successives, chacune parcourant toute la cascade géographique.

    PASSE 1 (nom exact) : commune -> département -> national
    PASSE 2 (règles souples) : commune -> département -> national

    L'ordre est délibéré : la QUALITÉ du match sur le nom prime sur la
    PROXIMITÉ géographique. Un nom exact trouvé au national est plus fiable
    qu'une correspondance approximative dans la commune de l'offre.

    Coût : jusqu'à 6 appels API par offre au lieu de 3, mais les résultats
    de chaque niveau sont mis en cache local pour éviter tout doublon.
    """
    if nom.strip().upper() in SIGLES_NON_MATCHABLES:
        return ("non_matchable_sigle_connu", None)

    # Les candidats de chaque niveau sont récupérés une seule fois et
    # réutilisés par les deux passes.
    niveaux = []

    if commune:
        candidats = chercher(nom, {"code_commune": commune})
        actifs = [r for r in candidats
                  if r.get("siege", {}).get("commune") == commune
                  and r.get("siege", {}).get("etat_administratif") == "A"]
        niveaux.append(("", actifs, True))

        dept = departement_depuis_commune(commune)
        if dept:
            candidats_d = chercher(nom, {"departement": dept})
            actifs_d = [r for r in candidats_d
                        if r.get("siege", {}).get("etat_administratif") == "A"]
            niveaux.append(("_dept", actifs_d, True))

    candidats_n = chercher(nom, {})
    actifs_n = [r for r in candidats_n
                if r.get("siege", {}).get("etat_administratif") == "A"]
    suffixe_national = "_national_sans_geo" if not commune else "_national"
    # autoriser_naf=False au national : voir docstring de _departager
    niveaux.append((suffixe_national, actifs_n, False))

    # PASSE 1 : nom exact sur tous les niveaux
    for suffixe, actifs, naf_ok in niveaux:
        issue = selectionner_nom_exact(nom, code_naf, actifs, naf_ok)
        if issue:
            return (issue[0] + suffixe, issue[1])

    # PASSE 2 : règles souples sur tous les niveaux
    for suffixe, actifs, naf_ok in niveaux:
        issue = selectionner_souple(nom, code_naf, actifs, naf_ok)
        if issue:
            return (issue[0] + suffixe, issue[1])

    return ("non_resolu_sans_geo" if not commune else "non_resolu", None)


def extraire_champs(candidat):
    """
    Ne conserve du retour API que les champs utiles à dim_entreprise.
    Le reste (dirigeants, finances, liste des établissements...) est hors
    scope et alourdirait inutilement le dump.
    """
    siege = candidat.get("siege", {})
    return {
        "siren": candidat.get("siren"),
        "siret_siege": siege.get("siret"),
        "nom_complet": candidat.get("nom_complet"),
        "code_naf": candidat.get("activite_principale"),
        "section_naf": candidat.get("section_activite_principale"),
        "tranche_effectif": candidat.get("tranche_effectif_salarie"),
        "annee_effectif": candidat.get("annee_tranche_effectif_salarie"),
        "categorie_entreprise": candidat.get("categorie_entreprise"),
        "date_creation": candidat.get("date_creation"),
        "nombre_etablissements": candidat.get("nombre_etablissements"),
        "commune_siege": siege.get("commune"),
        "code_postal_siege": siege.get("code_postal"),
    }


# ─────────────────────────────────────────────────────────────
# Programme principal
# ─────────────────────────────────────────────────────────────

def main():
    print("Lecture de la population cible depuis DuckDB...")

    # Lecture seule : aucun risque de verrou concurrent avec dbt
    con = duckdb.connect(CHEMIN_BASE, read_only=True)
    offres = con.execute("""
        select offre_id, entreprise_nom, commune, code_naf
        from fct_offre
        where categorie_employeur = 'EMPLOYEUR_DIRECT'
    """).fetchall()
    con.close()

    print(f"Population cible : {len(offres)} offres EMPLOYEUR_DIRECT")

    # Déduplication des appels : un même couple (nom, commune) revient
    # souvent (un employeur poste plusieurs offres au même endroit).
    # Le cache évite des dizaines d'appels API identiques.
    cache = {}
    resultats = []
    compteurs = {}

    for i, (offre_id, nom, commune, code_naf) in enumerate(offres, start=1):
        cle = (nom, commune, code_naf)

        if cle in cache:
            statut, candidat = cache[cle]
        else:
            try:
                statut, candidat = resoudre_entreprise(nom, commune, code_naf)
            except requests.exceptions.HTTPError as e:
                statut, candidat = "erreur_technique", None
                print(f"  erreur HTTP pour '{nom}' : {e}")
            cache[cle] = (statut, candidat)

        compteurs[statut] = compteurs.get(statut, 0) + 1

        resultats.append({
            "offre_id": offre_id,
            "entreprise_nom_offre": nom,
            "commune_offre": commune,
            "code_naf_offre": code_naf,
            "statut_matching": statut,
            "entreprise": extraire_champs(candidat) if candidat else None,
        })

        print(f"[{i}/{len(offres)}] {nom} -> {statut}")

    total_match = sum(n for s, n in compteurs.items() if s.startswith("match"))
    taux = 100 * total_match / len(offres)

    # Structure {metadata, resultats}, identique au dump d'ingestion
    # France Travail : cohérence des sources brutes.
    horodatage = datetime.now().strftime("%Y-%m-%d_%H%M")
    chemin_sortie = f"{DOSSIER_SORTIE}/enrichissement_dinum_{horodatage}.json"

    sortie = {
        "metadata": {
            "date_execution": datetime.now().isoformat(),
            "source": "API Recherche d'entreprises (DINUM)",
            "endpoint": URL_DINUM,
            "population_cible": "fct_offre where categorie_employeur = 'EMPLOYEUR_DIRECT'",
            "nb_offres": len(offres),
            "nb_appels_uniques": len(cache),
            "nb_matches": total_match,
            "taux_matching_pct": round(taux, 1),
            "repartition_statuts": compteurs,
        },
        "resultats": resultats,
    }

    with open(chemin_sortie, "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, indent=2)

# --- Audit qualité ---
    # Deux signaux complémentaires, appris du faux positif Paris-Saclay :
    #   1. mots de l'offre absents du candidat (match trop lâche)
    #   2. mots du candidat absents de l'offre (candidat trop large :
    #      "ASSOCIATION DES ETUDIANTS ... DE L'UNIVERSITE PARIS-SACLAY"
    #      contient tous les mots de "UNIVERSITE PARIS-SACLAY", mais en
    #      ajoute huit, signe qu'on a attrapé une entité satellite)
    print("\n--- Audit qualité ---")

    familles = {}
    suspects = []

    for r in resultats:
        if not r["entreprise"]:
            continue

        voie = r["statut_matching"]
        if "consolide_groupe" in voie:
            f = "consolidation groupe (arbitrage)"
        elif "mots_inclus" in voie:
            f = "inclusion de mots"
        elif "prefixe" in voie:
            f = "prefixe"
        else:
            f = "nom exact (le plus sûr)"
        familles[f] = familles.get(f, 0) + 1

        mots_offre = set(normaliser_nom(r["entreprise_nom_offre"]).split())
        if not mots_offre:
            continue

        # On mesure l'écart contre la variante la PLUS PROCHE, pas contre la
        # chaîne entière : DINUM empile toutes les enseignes dans nom_complet
        # ("ADECCO FRANCE (ADECCO FRANCE, LHH RECRUITMENT SOLUTIONS, AKKODIS
        # TALENT, QAPA)"), ce qui gonflait artificiellement le signal "en trop"
        # sur des matchs parfaits. L'audit s'aligne ainsi sur la logique de
        # matching, qui compare déjà variante par variante.
        meilleur = None
        for v in variantes_nom(r["entreprise"]["nom_complet"]):
            mots_v = set(v.split())
            if not mots_v:
                continue
            manquants = len(mots_offre - mots_v) / len(mots_offre)
            en_trop = len(mots_v - mots_offre) / len(mots_v)
            score = max(manquants, en_trop)
            if meilleur is None or score < meilleur[0]:
                meilleur = (score, manquants, en_trop)

        if meilleur is None:
            continue

        score, manquants, en_trop = meilleur
        if manquants > 0.5 or en_trop > 0.6:
            suspects.append((score, r, manquants, en_trop))

    print("\nRépartition par niveau de confiance :")
    for f, n in sorted(familles.items(), key=lambda x: -x[1]):
        print(f"  {f} : {n} ({100 * n / total_match:.1f}% des matchs)")

    print("\nMatchs à vérifier :")
    for score, r, manq, trop in sorted(suspects, key=lambda x: -x[0])[:15]:
        print(f"  [{manq:.0%} manquants, {trop:.0%} en trop] {r['entreprise_nom_offre']}")
        print(f"      -> {r['entreprise']['nom_complet']}  ({r['statut_matching']})")

    print(f"\nTotal matchs à vérifier : {len(suspects)} / {total_match}")

    print("\n--- Répartition des statuts ---")
    for statut, n in sorted(compteurs.items(), key=lambda x: -x[1]):
        print(f"  {statut} : {n} ({100 * n / len(offres):.1f}%)")

    print(f"\nTAUX DE MATCHING : {total_match}/{len(offres)} ({taux:.1f}%)")
    print(f"Appels API économisés par le cache : {len(offres) - len(cache)}")
    print(f"\nDump écrit : {chemin_sortie}")


if __name__ == "__main__":
    main()