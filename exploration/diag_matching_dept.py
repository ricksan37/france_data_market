"""
Enrichissement DINUM — diagnostic de matching (Phase 3, Session 5).

Mesure le taux de matching des offres EMPLOYEUR_DIRECT contre l'API
Recherche d'entreprises (DINUM), conformément à FR-014 / FR-015.

Stratégie construite par paliers mesurés (19,2% -> 80,8%) :
  - Clé géographique = code INSEE commune (§4.1), pas le code postal.
  - Cascade géographique : commune -> département -> national.
  - Comparaison sur variantes de nom (DINUM concatène raison sociale et
    enseignes entre parenthèses).
  - Normalisation : accents, ponctuation, mots vides, formes juridiques.
  - Correspondances souples : préfixe sur frontière de mot, inclusion de mots.
  - Disambiguant NAF, puis consolidation groupe sur homonymes.

Limites connues et assumées :
  - "EY" (28 offres) : sigle sans correspondance dans SIRENE.
  - Consolidation groupe : rattache à tort les homonymes sans lien capitalistique.
  - Repêchage NAF sans nom : voie la plus risquée, réduite à 1 cas.
"""

import duckdb
import requests
import time
import re
import unicodedata

URL_DINUM = "https://recherche-entreprises.api.gouv.fr/search"
MOTS_VIDES = {"DE", "LA", "LE", "DU", "DES", "ET", "D", "L"}

# Formes juridiques accolées à la raison sociale dans SIRENE, quasi jamais
# écrites par l'employeur dans l'offre (ex. "Keolis" vs "KEOLIS SA").
FORMES_JURIDIQUES = {
    "SA", "SAS", "SASU", "SARL", "EURL", "SNC", "SCS", "SCA",
    "SE", "SCOP", "SCIC", "GIE", "GEIE", "EARL", "SCI", "SEM",
    "SELARL", "SELAS", "SPRL", "GMBH", "LTD", "BV", "NV", "AG", "SPA",
}


def normaliser_nom(nom):
    """
    Neutralise ce qui varie entre le nom saisi par l'employeur et la raison
    sociale SIRENE : casse, accents, ponctuation, mots vides, forme juridique.

    Les accents sont critiques : SIRENE stocke sans accents ("DEFI RH")
    alors que l'offre les conserve.

    Garde-fou : on ne retire mots vides et formes juridiques que s'il reste
    au moins un mot. Certaines entreprises s'appellent littéralement "LTd".
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
    DINUM concatène raison sociale ET enseignes/sigles entre parenthèses :
    "LEIHIA (LEIHIA) (LEIHIA)", "AGENCE FRANCAISE DE DEVELOPPEMENT (AFD)".
    Comparer la chaîne entière échoue sur des correspondances parfaites.
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
    """
    if not court or not long:
        return False
    if court == long:
        return True
    return long.startswith(court + " ")


def mots_inclus(nom_court, nom_long):
    """
    Vrai si TOUS les mots de `nom_court` sont présents dans `nom_long`.

    Gère les mots insérés au milieu : "CAISSE EPARGNE LANGUEDOC ROUSSILLON"
    est inclus dans "CAISSE EPARGNE PREVOYANCE LANGUEDOC ROUSSILLON".

    Garde-fou : au moins 2 mots, pour éviter qu'un nom d'un seul mot
    générique soit inclus dans des dizaines de candidats.
    """
    mots_court = set(nom_court.split())
    if len(mots_court) < 2:
        return False
    return mots_court.issubset(set(nom_long.split()))


def departement_depuis_commune(code_commune):
    """Code département depuis le code INSEE. DOM : 97x/98x sur 3 chiffres."""
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
    time.sleep(1 / 7)
    return resp.json().get('results', [])


def consolider_groupe(candidats):
    """
    Départage des homonymes par nombre d'établissements.

    Objectif analytique du projet = caractériser le TYPE de structure qui
    recrute (secteur, taille, âge). Rattacher une offre d'une filiale
    régionale à sa maison mère est donc le comportement souhaité.

    Angle mort assumé : les homonymes SANS lien capitalistique sont
    rattachés à tort -> statut distinct pour mesurer ces cas en aval.
    """
    avec_etabs = [r for r in candidats if r.get('nombre_etablissements') is not None]
    if not avec_etabs:
        return None
    return max(avec_etabs, key=lambda r: r.get('nombre_etablissements', 0))


def selectionner(nom_offre, code_naf_offre, candidats_actifs):
    """
    Cascade sur des candidats déjà filtrés géographiquement.
    Retourne (statut, nom_matché) ou None.
    Le NAF sert UNIQUEMENT de disambiguant entre candidats déjà retenus par
    le nom. La voie "NAF seul, sans correspondance de nom" a été supprimée
    après audit : elle produisait 2 matchs sur 172, dont 2 douteux
    (TCCONCEPT-LRI -> TCRI GROUP, ECOLE DES MINES -> INSTITUT MINES-TELECOM).
    Règle retenue : le nom doit toujours corroborer le match.
    """
    if not candidats_actifs:
        return None

    nom_cible = normaliser_nom(nom_offre)
    par_nom = [r for r in candidats_actifs
               if nom_cible in variantes_nom(r.get('nom_complet', ''))]

    if len(par_nom) == 1:
        return ("match_nom", par_nom[0].get('nom_complet'))

    if len(par_nom) > 1:
        if code_naf_offre:
            par_naf = [r for r in par_nom if r.get('activite_principale') == code_naf_offre]
            if len(par_naf) == 1:
                return ("match_nom_puis_naf", par_naf[0].get('nom_complet'))
            if len(par_naf) > 1:
                par_nom = par_naf
        principal = consolider_groupe(par_nom)
        if principal:
            return ("match_consolide_groupe", principal.get('nom_complet'))
        return None

    # Préfixe dans les deux sens, sur frontière de mot
    par_prefixe = [
        r for r in candidats_actifs
        if any(est_prefixe_sur_mot(nom_cible, v) or est_prefixe_sur_mot(v, nom_cible)
               for v in variantes_nom(r.get('nom_complet', '')))
    ]

    if len(par_prefixe) == 1:
        return ("match_nom_prefixe", par_prefixe[0].get('nom_complet'))

    if len(par_prefixe) > 1:
        if code_naf_offre:
            par_naf = [r for r in par_prefixe if r.get('activite_principale') == code_naf_offre]
            if len(par_naf) == 1:
                return ("match_prefixe_puis_naf", par_naf[0].get('nom_complet'))
            if len(par_naf) > 1:
                par_prefixe = par_naf
        principal = consolider_groupe(par_prefixe)
        if principal:
            return ("match_consolide_groupe_prefixe", principal.get('nom_complet'))

    # Inclusion de mots : mots insérés au milieu de la raison sociale
    par_inclusion = [
        r for r in candidats_actifs
        if any(mots_inclus(nom_cible, v)
               for v in variantes_nom(r.get('nom_complet', '')))
    ]

    if len(par_inclusion) == 1:
        return ("match_mots_inclus", par_inclusion[0].get('nom_complet'))

    if len(par_inclusion) > 1:
        if code_naf_offre:
            par_naf = [r for r in par_inclusion
                       if r.get('activite_principale') == code_naf_offre]
            if len(par_naf) == 1:
                return ("match_mots_inclus_puis_naf", par_naf[0].get('nom_complet'))
            if len(par_naf) > 1:
                par_inclusion = par_naf
        principal = consolider_groupe(par_inclusion)
        if principal:
            return ("match_consolide_groupe_inclusion", principal.get('nom_complet'))

    return None


def selectionner_national(nom_offre, candidats_actifs, suffixe):
    """
    Sélection sans ancrage géographique. Plus prudente : jamais de repêchage
    par NAF seul, qui matcherait n'importe quelle entreprise du secteur.
    """
    if not candidats_actifs:
        return None

    nom_cible = normaliser_nom(nom_offre)
    par_nom = [r for r in candidats_actifs
               if nom_cible in variantes_nom(r.get('nom_complet', ''))]

    if len(par_nom) == 1:
        return ("match_nom" + suffixe, par_nom[0].get('nom_complet'))

    if len(par_nom) > 1:
        principal = consolider_groupe(par_nom)
        if principal:
            return ("match_consolide_groupe" + suffixe, principal.get('nom_complet'))
        return None

    par_prefixe = [
        r for r in candidats_actifs
        if any(est_prefixe_sur_mot(nom_cible, v) or est_prefixe_sur_mot(v, nom_cible)
               for v in variantes_nom(r.get('nom_complet', '')))
    ]

    if len(par_prefixe) == 1:
        return ("match_nom_prefixe" + suffixe, par_prefixe[0].get('nom_complet'))

    if len(par_prefixe) > 1:
        principal = consolider_groupe(par_prefixe)
        if principal:
            return ("match_consolide_groupe_prefixe" + suffixe, principal.get('nom_complet'))

    par_inclusion = [
        r for r in candidats_actifs
        if any(mots_inclus(nom_cible, v)
               for v in variantes_nom(r.get('nom_complet', '')))
    ]

    if len(par_inclusion) == 1:
        return ("match_mots_inclus" + suffixe, par_inclusion[0].get('nom_complet'))

    if len(par_inclusion) > 1:
        principal = consolider_groupe(par_inclusion)
        if principal:
            return ("match_consolide_groupe_inclusion" + suffixe,
                    principal.get('nom_complet'))

    return None


# --- Population cible ---
# À lancer depuis observatoire/ (chemin relatif ../data/)

con = duckdb.connect('../data/warehouse.duckdb', read_only=True)
offres = con.execute("""
    select entreprise_nom, commune, code_naf
    from fct_offre
    where categorie_employeur = 'EMPLOYEUR_DIRECT'
""").fetchall()
con.close()

print(f"Population cible : {len(offres)} offres")

compteurs = {}
exemples = {}
resultats_audit = []

for i, (nom, commune, code_naf) in enumerate(offres, start=1):

    if nom.strip().upper() == "EY":
        # Diagnostiqué Session 5 : sigle sans correspondance légale.
        statut, detail = "pas_de_resultat_sigle_connu", None
    else:
        issue = None
        detail_echec = None
        statut, detail = None, None

        try:
            if commune:
                # NIVEAU 1 : commune exacte
                resultats = chercher(nom, {"code_commune": commune})
                actifs = [r for r in resultats
                          if r.get('siege', {}).get('commune') == commune
                          and r.get('siege', {}).get('etat_administratif') == 'A']
                issue = selectionner(nom, code_naf, actifs)

                # NIVEAU 2 : élargissement au département
                if issue is None:
                    dept = departement_depuis_commune(commune)
                    if dept:
                        resultats_d = chercher(nom, {"departement": dept})
                        actifs_d = [r for r in resultats_d
                                    if r.get('siege', {}).get('etat_administratif') == 'A']
                        issue = selectionner(nom, code_naf, actifs_d)
                        if issue:
                            issue = (issue[0] + "_dept", issue[1])

            # NIVEAU 3 : national, dernier recours (et seul recours sans géo)
            if issue is None:
                resultats_n = chercher(nom, {})
                actifs_n = [r for r in resultats_n
                            if r.get('siege', {}).get('etat_administratif') == 'A']
                suffixe = "_national_sans_geo" if not commune else "_national"
                issue = selectionner_national(nom, actifs_n, suffixe)
                if issue is None:
                    detail_echec = [r.get('nom_complet') for r in actifs_n][:3]

            if issue:
                statut, detail = issue
            else:
                statut = "non_resolu_sans_geo" if not commune else "non_resolu"
                detail = detail_echec

        except requests.exceptions.HTTPError as e:
            statut, detail = "erreur_technique", str(e)

    compteurs[statut] = compteurs.get(statut, 0) + 1
    exemples.setdefault(statut, [])
    if len(exemples[statut]) < 70:
        exemples[statut].append((nom, detail))

    # Collecte pour l'audit qualité
    if statut and statut.startswith("match") and isinstance(detail, str):
        resultats_audit.append({
            "nom_offre": nom,
            "nom_matche": detail,
            "voie": statut,
            "naf_offre": code_naf,
        })

    print(f"[{i}/{len(offres)}] {nom} -> {statut}")


# --- Métrique de qualité (FR-015) ---

print("\n--- Résultat détaillé ---")
total_match = 0
for statut, count in sorted(compteurs.items(), key=lambda x: -x[1]):
    pct = 100 * count / len(offres)
    print(f"{statut} : {count} ({pct:.1f}%)")
    if statut and statut.startswith("match"):
        total_match += count
print(f"\nTOTAL MATCH : {total_match} ({100 * total_match / len(offres):.1f}%)")


# --- Audit qualité : détection des matchs suspects ---

print("\n" + "=" * 60)
print("AUDIT QUALITÉ")
print("=" * 60)

familles = {}
for r in resultats_audit:
    if "consolide_groupe" in r["voie"]:
        f = "consolidation groupe (arbitrage)"
    elif "naf_sans_nom" in r["voie"]:
        f = "NAF seul (le plus risqué)"
    elif "mots_inclus" in r["voie"]:
        f = "inclusion de mots"
    elif "prefixe" in r["voie"]:
        f = "prefixe"
    else:
        f = "nom exact (le plus sûr)"
    familles[f] = familles.get(f, 0) + 1

print("\nRépartition par niveau de confiance :")
for f, n in sorted(familles.items(), key=lambda x: -x[1]):
    print(f"  {f} : {n} ({100 * n / len(resultats_audit):.1f}% des matchs)")

print("\nMatchs avec écart de nom important (à vérifier à l'oeil) :")
suspects = []
for r in resultats_audit:
    mots_offre = set(normaliser_nom(r["nom_offre"]).split())
    mots_matche = set(normaliser_nom(r["nom_matche"]).split())
    if not mots_offre:
        continue
    taux_commun = len(mots_offre & mots_matche) / len(mots_offre)
    if taux_commun < 0.5:
        suspects.append((taux_commun, r))

for taux, r in sorted(suspects, key=lambda x: x[0])[:20]:
    print(f"  [{taux:.0%} commun] {r['nom_offre']}")
    print(f"      -> {r['nom_matche']}  ({r['voie']})")

print(f"\nTotal matchs à écart important : {len(suspects)} / {len(resultats_audit)}")