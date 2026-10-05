"""
DINUM enrichment: matching diagnostic (Phase 3).

Measures the matching rate of DIRECT_EMPLOYER offers against the Recherche
d'entreprises API (DINUM), in line with FR-014 / FR-015.

Strategy built in measured steps (19.2% -> 80.8%):
  - Geographic key = commune INSEE code (§4.1), not the postal code.
  - Geographic cascade: commune -> department -> national.
  - Comparison on name variants (DINUM concatenates the legal name and the
    trade names in parentheses).
  - Normalization: accents, punctuation, stop words, legal forms.
  - Loose matches: prefix on a word boundary, word inclusion.
  - NAF tiebreaker, then group consolidation on homonyms.

Known and accepted limits:
  - "EY" (28 offers): acronym with no counterpart in SIRENE.
  - Group consolidation: wrongly attaches homonyms with no capital link.
  - NAF recovery without a name: the riskiest route, reduced to 1 case.
"""

import duckdb
import requests
import time
import re
import unicodedata

URL_DINUM = "https://recherche-entreprises.api.gouv.fr/search"
MOTS_VIDES = {"DE", "LA", "LE", "DU", "DES", "ET", "D", "L"}

# Legal forms attached to the legal name in SIRENE, almost never written by
# the employer in the offer (e.g. "Keolis" vs "KEOLIS SA").
FORMES_JURIDIQUES = {
    "SA", "SAS", "SASU", "SARL", "EURL", "SNC", "SCS", "SCA",
    "SE", "SCOP", "SCIC", "GIE", "GEIE", "EARL", "SCI", "SEM",
    "SELARL", "SELAS", "SPRL", "GMBH", "LTD", "BV", "NV", "AG", "SPA",
}


def normaliser_nom(nom):
    """
    Neutralizes what varies between the name typed by the employer and the
    SIRENE legal name: case, accents, punctuation, stop words, legal form.

    Accents are critical: SIRENE stores names without accents ("DEFI RH")
    while the offer keeps them.

    Safeguard: stop words and legal forms are only removed if at least one
    word remains. Some companies are literally called "LTd".
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
    DINUM concatenates the legal name AND trade names/acronyms in parentheses:
    "LEIHIA (LEIHIA) (LEIHIA)", "AGENCE FRANCAISE DE DEVELOPPEMENT (AFD)".
    Comparing the whole string fails on perfect matches.
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
    True if `court` is a prefix of `long` ending on a whole word.

    "STEP UP" is a prefix of "STEP UP LILLE" (followed by a space).
    "FED" is NOT a prefix of "FEDERATION SPORTIVE" (cuts mid-word).
    """
    if not court or not long:
        return False
    if court == long:
        return True
    return long.startswith(court + " ")


def mots_inclus(nom_court, nom_long):
    """
    True if ALL the words of `nom_court` are present in `nom_long`.

    Handles words inserted in the middle: "CAISSE EPARGNE LANGUEDOC ROUSSILLON"
    is included in "CAISSE EPARGNE PREVOYANCE LANGUEDOC ROUSSILLON".

    Safeguard: at least 2 words, to prevent a single generic word from being
    included in dozens of candidates.
    """
    mots_court = set(nom_court.split())
    if len(mots_court) < 2:
        return False
    return mots_court.issubset(set(nom_long.split()))


def departement_depuis_commune(code_commune):
    """Department code from the INSEE code. Overseas: 97x/98x on 3 digits."""
    if not code_commune:
        return None
    if code_commune.startswith("97") or code_commune.startswith("98"):
        return code_commune[:3]
    return code_commune[:2]


def chercher(nom, params_geo):
    """One API call with a given set of geographic parameters."""
    params = {"q": nom, **params_geo}
    resp = requests.get(URL_DINUM, params=params)
    resp.raise_for_status()
    time.sleep(1 / 7)
    return resp.json().get('results', [])


def consolider_groupe(candidats):
    """
    Tiebreak among homonyms by number of establishments.

    The project's analytical goal = characterize the TYPE of organization that
    hires (sector, size, age). Attaching an offer from a regional subsidiary to
    its parent company is therefore the desired behavior.

    Accepted blind spot: homonyms WITH NO capital link are wrongly attached
    -> distinct status to measure these cases downstream.
    """
    avec_etabs = [r for r in candidats if r.get('nombre_etablissements') is not None]
    if not avec_etabs:
        return None
    return max(avec_etabs, key=lambda r: r.get('nombre_etablissements', 0))


def selectionner(nom_offre, naf_code_on_offer, candidats_actifs):
    """
    Cascade over candidates already filtered geographically.
    Returns (status, matched_name) or None.
    The NAF serves ONLY as a tiebreaker among candidates already retained by
    name. The "NAF alone, without a name match" route was removed after audit:
    it produced 2 matches out of 172, of which 2 doubtful
    (TCCONCEPT-LRI -> TCRI GROUP, ECOLE DES MINES -> INSTITUT MINES-TELECOM).
    Rule kept: the name must always corroborate the match.
    """
    if not candidats_actifs:
        return None

    nom_cible = normaliser_nom(nom_offre)
    par_nom = [r for r in candidats_actifs
               if nom_cible in variantes_nom(r.get('nom_complet', ''))]

    if len(par_nom) == 1:
        return ("match_nom", par_nom[0].get('nom_complet'))

    if len(par_nom) > 1:
        if naf_code_on_offer:
            par_naf = [r for r in par_nom if r.get('activite_principale') == naf_code_on_offer]
            if len(par_naf) == 1:
                return ("match_nom_puis_naf", par_naf[0].get('nom_complet'))
            if len(par_naf) > 1:
                par_nom = par_naf
        principal = consolider_groupe(par_nom)
        if principal:
            return ("match_consolide_groupe", principal.get('nom_complet'))
        return None

    # Prefix in both directions, on a word boundary
    par_prefixe = [
        r for r in candidats_actifs
        if any(est_prefixe_sur_mot(nom_cible, v) or est_prefixe_sur_mot(v, nom_cible)
               for v in variantes_nom(r.get('nom_complet', '')))
    ]

    if len(par_prefixe) == 1:
        return ("match_nom_prefixe", par_prefixe[0].get('nom_complet'))

    if len(par_prefixe) > 1:
        if naf_code_on_offer:
            par_naf = [r for r in par_prefixe if r.get('activite_principale') == naf_code_on_offer]
            if len(par_naf) == 1:
                return ("match_prefixe_puis_naf", par_naf[0].get('nom_complet'))
            if len(par_naf) > 1:
                par_prefixe = par_naf
        principal = consolider_groupe(par_prefixe)
        if principal:
            return ("match_consolide_groupe_prefixe", principal.get('nom_complet'))

    # Word inclusion: words inserted in the middle of the legal name
    par_inclusion = [
        r for r in candidats_actifs
        if any(mots_inclus(nom_cible, v)
               for v in variantes_nom(r.get('nom_complet', '')))
    ]

    if len(par_inclusion) == 1:
        return ("match_mots_inclus", par_inclusion[0].get('nom_complet'))

    if len(par_inclusion) > 1:
        if naf_code_on_offer:
            par_naf = [r for r in par_inclusion
                       if r.get('activite_principale') == naf_code_on_offer]
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
    Selection without a geographic anchor. More cautious: never a recovery by
    NAF alone, which would match any company in the sector.
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


# --- Target population ---
# Run from france_data_market/ (relative path ../data/)

con = duckdb.connect('../data/warehouse.duckdb', read_only=True)
offres = con.execute("""
    select employer_name, commune_code, naf_code
    from fct_job_offer
    where employer_category = 'DIRECT_EMPLOYER'
""").fetchall()
con.close()

print(f"Population cible : {len(offres)} offres")

compteurs = {}
exemples = {}
resultats_audit = []

for i, (nom, commune, naf_code) in enumerate(offres, start=1):

    if nom.strip().upper() == "EY":
        # Already diagnosed: acronym with no legal counterpart.
        statut, detail = "pas_de_resultat_sigle_connu", None
    else:
        issue = None
        detail_echec = None
        statut, detail = None, None

        try:
            if commune:
                # LEVEL 1: exact commune
                resultats = chercher(nom, {"code_commune": commune})
                actifs = [r for r in resultats
                          if r.get('siege', {}).get('commune') == commune
                          and r.get('siege', {}).get('etat_administratif') == 'A']
                issue = selectionner(nom, naf_code, actifs)

                # LEVEL 2: widening to the department
                if issue is None:
                    dept = departement_depuis_commune(commune)
                    if dept:
                        resultats_d = chercher(nom, {"departement": dept})
                        actifs_d = [r for r in resultats_d
                                    if r.get('siege', {}).get('etat_administratif') == 'A']
                        issue = selectionner(nom, naf_code, actifs_d)
                        if issue:
                            issue = (issue[0] + "_dept", issue[1])

            # LEVEL 3: national, last resort (and the only one without geo)
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

    # Collection for the quality audit
    if statut and statut.startswith("match") and isinstance(detail, str):
        resultats_audit.append({
            "nom_offre": nom,
            "nom_matche": detail,
            "voie": statut,
            "naf_offre": naf_code,
        })

    print(f"[{i}/{len(offres)}] {nom} -> {statut}")


# --- Quality metric (FR-015) ---

print("\n--- Résultat détaillé ---")
total_match = 0
for statut, count in sorted(compteurs.items(), key=lambda x: -x[1]):
    pct = 100 * count / len(offres)
    print(f"{statut} : {count} ({pct:.1f}%)")
    if statut and statut.startswith("match"):
        total_match += count
print(f"\nTOTAL MATCH : {total_match} ({100 * total_match / len(offres):.1f}%)")


# --- Quality audit: detection of suspicious matches ---

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