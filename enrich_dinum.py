"""
Company enrichment via the Company Search API (DINUM).

Enriches DIRECT_EMPLOYER offers with SIREN, NAF, headcount and creation
date, by resolving the employer name entered by the employer to a legal
entity in the SIRENE registry. The API is public and needs no credentials.
Figures below: 2026-09-26 run, 707 offers, 86.8% matched.

MATCHING STRATEGY:

  Geographic key: INSEE commune code, not the postal code. It is populated
    more often (250 vs 236 of the 267 direct-employer offers of the
    2026-09-26 job offers dump) and maps 1:1 to a commune, which a postal
    code does not.

  Geographic cascade: commune -> department -> national.
    The registered head office is often outside the offer's commune
    (universities, regional banks, national groups).

  Name comparison, from strictest to loosest:
    1. exact name, across variants (DINUM concatenates the legal name AND
       trade names/acronyms in parentheses)
    2. prefix on a word boundary (truncation on France Travail's side, or a
       word added by the employer)
    3. word inclusion (a word inserted in the middle of the legal name)

  NAF is used ONLY as a tiebreaker among candidates already retained by
  name: the name must always corroborate. A NAF-only match was measured at
  2 matches out of 172, both doubtful.

  Group consolidation on homonyms: the entity with the largest number of
  establishments is kept. Aligned with the project's analytical goal
  (characterizing the TYPE of structure that's hiring): a KEOLIS SUD
  LORRAINE offer does belong to a large transport group.

KNOWN AND ACCEPTED LIMITS:
  - "EY" (40 offers, 5.7%): a commercial acronym absent from SIRENE, and 5+
    legal entities in the group with no tiebreaking criterion. Deliberately
    not matched.
  - Internal department labels ("FONCTIONS SUPPORTS", "751163-DIR STRATEGIE
    INNOVATION ET TRANSFO", "BNP Paribas Mission Handicap"): these aren't
    company names, no rule can attach them correctly. Any rule loose enough
    to find them a candidate will find a WRONG candidate (a works council, a
    satellite association). Not filtered upstream: the criterion would rely
    on a keyword list built from a handful of examples.
  - Group consolidation (73 matches, 11.9% of matches): wrongly attaches
    homonyms with no capital link. Distinct status to filter downstream.
  - 53 offers (7.5%) unresolved: trade name or internal label absent from
    the SIRENE registry.

USAGE: run from the project ROOT; takes no argument.
    python3 enrich_dinum.py
"""

import argparse
import duckdb
import requests
import time
import re
import json
import unicodedata
from datetime import datetime

DINUM_URL = "https://recherche-entreprises.api.gouv.fr/search"
DB_PATH = "data/warehouse.duckdb"
OUTPUT_DIR = "data/raw"

# DINUM rate limit: 7 req/s per IP, HTTP 429 beyond that
DELAY_BETWEEN_CALLS = 1 / 7

# Transient failures: the 2026-09-26 run (929 offers, 4x the July population)
# died at offer 61 on a "connection reset by peer" during the TLS handshake,
# with nothing written -- the API answered normally seconds later. Retried
# with growing waits (5, 15, 45, 90 s) on network errors, 429 and 5xx; any
# other HTTP error, or a failure persisting past the last try, still raises.
# The 2026-10-05 CI run (263 offers) left 14 offers in 429 through waits of
# 2 to 16 s: the limit is shared by the runner's IP and outlasts 30 s.
MAX_ATTEMPTS = 5
RETRY_WAITS_SECONDS = (5, 15, 45, 90)
REQUEST_TIMEOUT_SECONDS = 30

STOP_WORDS = {"DE", "LA", "LE", "DU", "DES", "ET", "D", "L"}

# Legal forms appended to the legal name in SIRENE, almost never written by
# the employer in the offer (e.g. "Keolis" vs "KEOLIS SA").
LEGAL_FORMS = {
    "SA", "SAS", "SASU", "SARL", "EURL", "SNC", "SCS", "SCA",
    "SE", "SCOP", "SCIC", "GIE", "GEIE", "EARL", "SCI", "SEM",
    "SELARL", "SELAS", "SPRL", "GMBH", "LTD", "BV", "NV", "AG", "SPA",
}

# Known acronyms with no usable match in SIRENE.
# Documented rather than worked around: see KNOWN LIMITS above.
NON_MATCHABLE_ACRONYMS = {"EY"}


# ─────────────────────────────────────────────────────────────
# Name normalization and comparison
# ─────────────────────────────────────────────────────────────

def normalize_name(name):
    """
    Neutralizes what varies between the name entered by the employer and
    SIRENE's legal name: case, accents, punctuation, stop words, legal form.

    Accents are critical: SIRENE stores names without accents ("DEFI RH",
    "CREDIT AGRICOLE ASSURANCES") while the offer keeps them.

    Safeguard: stop words and legal forms are only stripped if at least one
    word remains. Some companies are literally named "LTd"; stripping them
    would empty the name and make any comparison impossible.

    Returns:
        The normalized name, words separated by single spaces.
    """
    name = name.strip().upper()

    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")

    name = re.sub(r"[.,'\-&]", " ", name)

    words = name.split()
    filtered_words = [w for w in words
                       if w not in STOP_WORDS and w not in LEGAL_FORMS]

    return " ".join(filtered_words) if filtered_words else " ".join(words)


def name_variants(full_name):
    """
    DINUM concatenates into nom_complet the legal name AND trade names or
    acronyms in parentheses: "LEIHIA (LEIHIA) (LEIHIA)", "AGENCE FRANCAISE
    DE DEVELOPPEMENT (AFD)". Comparing the whole string therefore fails on
    otherwise perfect matches.

    Returns:
        The set of every comparable normalized form: the whole string, the
        legal name alone, and each parenthesized content in isolation.
    """
    forms = {normalize_name(full_name)}
    forms.add(normalize_name(re.sub(r"\([^)]*\)", " ", full_name)))
    for content in re.findall(r"\(([^)]*)\)", full_name):
        for piece in content.split(","):
            form = normalize_name(piece)
            if form:
                forms.add(form)
    return {f for f in forms if f}


def is_prefix_on_word_boundary(short_name, long_name):
    """
    True if `short_name` is a prefix of `long_name` stopping on a whole word.

    "STEP UP" is a prefix of "STEP UP LILLE" (followed by a space).
    "FED" is NOT a prefix of "FEDERATION SPORTIVE" (cuts mid-word).

    A word boundary rather than a minimum length: it is impossible to match
    on a truncated word.

    Returns:
        True or False.
    """
    if not short_name or not long_name:
        return False
    if short_name == long_name:
        return True
    return long_name.startswith(short_name + " ")


def words_included(short_name, long_name):
    """
    True if EVERY word of `short_name` is present in `long_name`.

    Handles words inserted in the middle, which a prefix check can't catch:
    "CAISSE EPARGNE LANGUEDOC ROUSSILLON" is included in
    "CAISSE EPARGNE PREVOYANCE LANGUEDOC ROUSSILLON".

    Two safeguards:
    - at least 2 words, to avoid a single generic-word name matching dozens
      of candidates;
    - the candidate must not have more than double the word count. Without
      this bound, an internal department label like "FONCTIONS SUPPORTS"
      attaches to "AIDE AUX FONCTIONS SUPPORTS DES ENTREPRISES": strictly
      true inclusion, but an unrelated entity. A gap this large signals a
      satellite entity was caught, not the employer.

    Returns:
        True or False.
    """
    short_words = set(short_name.split())
    if len(short_words) < 2:
        return False

    long_words = set(long_name.split())
    if not short_words.issubset(long_words):
        return False

    return len(long_words) <= 2 * len(short_words)


# ─────────────────────────────────────────────────────────────
# API calls
# ─────────────────────────────────────────────────────────────

def department_from_commune(commune_code):
    """
    Department code from the INSEE commune code.
    Overseas territory case: codes in 97x / 98x -> 3-digit department.

    Returns:
        The department code, or None when commune_code is empty.
    """
    if not commune_code:
        return None
    if commune_code.startswith("97") or commune_code.startswith("98"):
        return commune_code[:3]
    return commune_code[:2]


def search(name, geo_params):
    """
    A single API search with a given set of geographic parameters, retried
    on transient failures.

    Returns:
        The list of candidate companies (the response's "results"), possibly
        empty.

    Raises:
        requests.HTTPError: non-retryable HTTP error, or a 429 / 5xx still
            failing after MAX_ATTEMPTS; the message carries the status code
            and the response body.
        requests.ConnectionError, requests.Timeout: network failure still
            present after MAX_ATTEMPTS.
    """
    params = {"q": name, **geo_params}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        retry_after = ""
        try:
            resp = requests.get(DINUM_URL, params=params,
                                timeout=REQUEST_TIMEOUT_SECONDS)
            retryable = resp.status_code == 429 or resp.status_code >= 500
            if not retryable or attempt == MAX_ATTEMPTS:
                # Not raise_for_status(): it drops the body, where the API
                # explains a refusal.
                if not resp.ok:
                    raise requests.HTTPError(
                        f"DINUM search refused ({resp.status_code}) for "
                        f"{name!r}: body={resp.text!r}",
                        response=resp,
                    )
                break
            reason = f"HTTP {resp.status_code}"
            retry_after = resp.headers.get("Retry-After", "")
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as err:
            if attempt == MAX_ATTEMPTS:
                raise
            reason = type(err).__name__
        wait = RETRY_WAITS_SECONDS[attempt - 1]
        # Not observed on a 200 (checked 2026-10-05): honoured if the API
        # sends it on a 429, ignored otherwise.
        if retry_after.isdigit():
            wait = max(wait, int(retry_after))
        print(f"  {reason} for '{name}', retry {attempt}/{MAX_ATTEMPTS - 1} in {wait}s")
        time.sleep(wait)
    time.sleep(DELAY_BETWEEN_CALLS)
    return resp.json().get("results", [])


# ─────────────────────────────────────────────────────────────
# Candidate selection
# ─────────────────────────────────────────────────────────────

def consolidate_group(candidates):
    """
    Breaks ties among homonyms by number of establishments.

    The project's analytical goal is to characterize the TYPE of structure
    hiring (sector, size, age). Attaching an offer from a regional
    subsidiary to its parent company is therefore the desired behavior, not
    a regrettable approximation.

    Accepted blind spot: homonyms with NO capital link get wrongly attached
    -> distinct status to measure and filter downstream.

    Returns:
        The candidate with the most establishments, or None when no
        candidate reports an establishment count.
    """
    with_establishments = [r for r in candidates if r.get("nombre_etablissements") is not None]
    if not with_establishments:
        return None
    return max(with_establishments, key=lambda r: r.get("nombre_etablissements", 0))


def _break_tie(candidates, offer_naf_code, naf_status, group_status, allow_naf):
    """
    Breaks ties among a set of candidates already retained by name.
    Common factor across the three matching modes.

    `allow_naf` is False at the national level: with no geographic anchor,
    a NAF match would bring together same-sector companies located
    anywhere.

    Returns:
        A (match_status, candidate) tuple, or None when no candidate can be
        chosen.
    """
    if len(candidates) == 1:
        return (naf_status.replace("_then_naf", ""), candidates[0])

    if allow_naf and offer_naf_code:
        by_naf = [r for r in candidates
                  if r.get("activite_principale") == offer_naf_code]
        if len(by_naf) == 1:
            return (naf_status, by_naf[0])
        if len(by_naf) > 1:
            candidates = by_naf

    leading_candidate = consolidate_group(candidates)
    if leading_candidate:
        return (group_status, leading_candidate)
    return None


def select_exact_name(offer_name, offer_naf_code, active_candidates, allow_naf=True):
    """
    PASS 1: exact name match only.

    Run across the whole geographic cascade BEFORE any fuzzy rule: an exact
    name found nationally is more reliable than an approximate match in the
    offer's own commune.

    Counter-example this separation handles: "UNIVERSITE PARIS-SACLAY"
    matches by word inclusion with "ASSOCIATION DES ETUDIANTS ... DE
    L'UNIVERSITE PARIS-SACLAY" in the right commune; a single pass would
    stop there instead of finding the university itself at the department
    level.

    Returns:
        A (match_status, candidate) tuple, or None when no candidate has
        the exact name.
    """
    if not active_candidates:
        return None

    target_name = normalize_name(offer_name)
    by_name = [r for r in active_candidates
               if target_name in name_variants(r.get("nom_complet", ""))]

    if not by_name:
        return None

    return _break_tie(by_name, offer_naf_code,
                       "match_name_then_naf", "match_consolidated_group",
                       allow_naf)


def select_fuzzy(offer_name, offer_naf_code, active_candidates, allow_naf=True):
    """
    PASS 2: loosened matches, in decreasing order of reliability: prefix on
    a word boundary, then word inclusion.

    Only attempted after the exact pass fails at EVERY geographic level.

    Returns:
        A (match_status, candidate) tuple, or None when no loosened rule
        finds a candidate.
    """
    if not active_candidates:
        return None

    target_name = normalize_name(offer_name)

    by_prefix = [
        r for r in active_candidates
        if any(is_prefix_on_word_boundary(target_name, v) or is_prefix_on_word_boundary(v, target_name)
               for v in name_variants(r.get("nom_complet", "")))
    ]
    if by_prefix:
        outcome = _break_tie(by_prefix, offer_naf_code,
                              "match_prefix_then_naf", "match_consolidated_group_prefix",
                              allow_naf)
        if outcome:
            return (outcome[0].replace("match_prefix", "match_name_prefix"), outcome[1])

    by_inclusion = [
        r for r in active_candidates
        if any(words_included(target_name, v)
               for v in name_variants(r.get("nom_complet", "")))
    ]
    if by_inclusion:
        return _break_tie(by_inclusion, offer_naf_code,
                           "match_word_inclusion_then_naf",
                           "match_consolidated_group_inclusion",
                           allow_naf)

    return None


def resolve_company(name, commune_code, naf_code):
    """
    Two successive passes, each running across the whole geographic
    cascade.

    PASS 1 (exact name): commune -> department -> national
    PASS 2 (fuzzy rules): commune -> department -> national

    The order is deliberate: match QUALITY on the name outweighs
    geographic PROXIMITY. An exact name found nationally is more reliable
    than an approximate match in the offer's own commune.

    Cost: up to 3 API calls per offer (one per geographic level); both
    passes reuse each level's candidates.

    Returns:
        A (match_status, candidate) tuple; candidate is None for the
        non_matchable_known_acronym, unresolved and unresolved_no_geo
        statuses.

    Raises:
        requests.HTTPError, requests.ConnectionError, requests.Timeout:
            propagated from search().
    """
    if name.strip().upper() in NON_MATCHABLE_ACRONYMS:
        return ("non_matchable_known_acronym", None)

    # Each level's candidates are fetched once and reused by both passes.
    levels = []

    if commune_code:
        candidates = search(name, {"code_commune": commune_code})
        active = [r for r in candidates
                  if r.get("siege", {}).get("commune") == commune_code
                  and r.get("siege", {}).get("etat_administratif") == "A"]
        levels.append(("", active, True))

        dept = department_from_commune(commune_code)
        if dept:
            dept_candidates = search(name, {"departement": dept})
            dept_active = [r for r in dept_candidates
                           if r.get("siege", {}).get("etat_administratif") == "A"]
            levels.append(("_dept", dept_active, True))

    national_candidates = search(name, {})
    national_active = [r for r in national_candidates
                       if r.get("siege", {}).get("etat_administratif") == "A"]
    national_suffix = "_national_no_geo" if not commune_code else "_national"
    # allow_naf=False at the national level: see _break_tie's docstring
    levels.append((national_suffix, national_active, False))

    # PASS 1: exact name at every level
    for suffix, active, naf_allowed in levels:
        outcome = select_exact_name(name, naf_code, active, naf_allowed)
        if outcome:
            return (outcome[0] + suffix, outcome[1])

    # PASS 2: fuzzy rules at every level
    for suffix, active, naf_allowed in levels:
        outcome = select_fuzzy(name, naf_code, active, naf_allowed)
        if outcome:
            return (outcome[0] + suffix, outcome[1])

    return ("unresolved_no_geo" if not commune_code else "unresolved", None)


def extract_fields(candidate):
    """
    Keeps only the API response fields useful to dim_company.
    The rest (executives, financials, list of establishments...) is out of
    scope and would needlessly bloat the dump.

    Returns:
        A dict of the 12 kept fields (None where the API has no value).
    """
    headquarters = candidate.get("siege", {})
    return {
        "siren": candidate.get("siren"),
        "headquarters_siret": headquarters.get("siret"),
        "full_name": candidate.get("nom_complet"),
        "naf_code": candidate.get("activite_principale"),
        "naf_section": candidate.get("section_activite_principale"),
        "employee_count_range": candidate.get("tranche_effectif_salarie"),
        "employee_count_reference_year": candidate.get("annee_tranche_effectif_salarie"),
        "company_category": candidate.get("categorie_entreprise"),
        "creation_date": candidate.get("date_creation"),
        "establishment_count": candidate.get("nombre_etablissements"),
        "headquarters_commune": headquarters.get("commune"),
        "headquarters_postal_code": headquarters.get("code_postal"),
    }


# ─────────────────────────────────────────────────────────────
# Main program
# ─────────────────────────────────────────────────────────────

def print_quality_audit(results, total_matches):
    """
    Prints the breakdown of matches by confidence level and the matches
    whose names diverge most, for a human review of the dump just written.

    Two complementary signals, learned from the Paris-Saclay false
    positive:
      1. offer words absent from the candidate (too loose a match)
      2. candidate words absent from the offer (too broad a candidate:
         "ASSOCIATION DES ETUDIANTS ... DE L'UNIVERSITE PARIS-SACLAY"
         contains every word of "UNIVERSITE PARIS-SACLAY", but adds eight
         more, a sign a satellite entity was caught)

    Returns:
        None.
    """
    print("\n--- Quality audit ---")

    families = {}
    suspects = []

    for r in results:
        if not r["company"]:
            continue

        path = r["match_status"]
        if "consolidated_group" in path:
            family = "group consolidation (arbitration)"
        elif "word_inclusion" in path:
            family = "word inclusion"
        elif "prefix" in path:
            family = "prefix"
        else:
            family = "exact name (safest)"
        families[family] = families.get(family, 0) + 1

        offer_words = set(normalize_name(r["employer_name_on_offer"]).split())
        if not offer_words:
            continue

        # The gap is measured against the CLOSEST variant, not the whole
        # string: DINUM stacks every trade name into nom_complet ("ADECCO
        # FRANCE (ADECCO FRANCE, LHH RECRUITMENT SOLUTIONS, AKKODIS TALENT,
        # QAPA)"), which would inflate the "extra words" signal on perfect
        # matches. The audit thus aligns with the matching logic, which
        # already compares variant by variant.
        best = None
        for v in name_variants(r["company"]["full_name"]):
            variant_words = set(v.split())
            if not variant_words:
                continue
            missing = len(offer_words - variant_words) / len(offer_words)
            extra = len(variant_words - offer_words) / len(variant_words)
            score = max(missing, extra)
            if best is None or score < best[0]:
                best = (score, missing, extra)

        if best is None:
            continue

        score, missing, extra = best
        if missing > 0.5 or extra > 0.6:
            suspects.append((score, r, missing, extra))

    print("\nBreakdown by confidence level:")
    for family, n in sorted(families.items(), key=lambda x: -x[1]):
        print(f"  {family}: {n} ({100 * n / total_matches:.1f}% of matches)")

    print("\nMatches to review:")
    for score, r, missing, extra in sorted(suspects, key=lambda x: -x[0])[:15]:
        print(f"  [{missing:.0%} missing, {extra:.0%} extra] {r['employer_name_on_offer']}")
        print(f"      -> {r['company']['full_name']}  ({r['match_status']})")

    print(f"\nTotal matches to review: {len(suspects)} / {total_matches}")


def main():
    """
    Enriches every DIRECT_EMPLOYER offer of fct_job_offer and writes one
    timestamped dump to data/raw/. An HTTP error on one offer is recorded
    as technical_error (which then fails dbt build) rather than stopping the
    run; a network failure that outlasts the retries stops it with nothing
    written.

    Returns:
        None.

    Raises:
        SystemExit: the target population is empty (no dump written).
        requests.ConnectionError, requests.Timeout: propagated from search().
    """
    print("Reading the target population from DuckDB...")

    # Read-only: no risk of a concurrent lock with dbt
    con = duckdb.connect(DB_PATH, read_only=True)
    offers = con.execute("""
        select job_offer_id, employer_name, commune_code, naf_code
        from fct_job_offer
        where employer_category = 'DIRECT_EMPLOYER'
    """).fetchall()
    con.close()

    print(f"Target population: {len(offers)} DIRECT_EMPLOYER offers")

    # An empty dump would become the latest one and empty stg_dinum__companies.
    if not offers:
        raise SystemExit("No DIRECT_EMPLOYER offer in fct_job_offer: run dbt build first. No dump written.")

    # Call deduplication: the same (name, commune) pair often recurs (an
    # employer posts several offers at the same location). The cache avoids
    # dozens of identical API calls.
    cache = {}
    results = []
    counters = {}

    for i, (offer_id, name, commune_code, naf_code) in enumerate(offers, start=1):
        key = (name, commune_code, naf_code)

        if key in cache:
            status, candidate = cache[key]
        else:
            try:
                status, candidate = resolve_company(name, commune_code, naf_code)
            except requests.exceptions.HTTPError as e:
                status, candidate = "technical_error", None
                print(f"  HTTP error for '{name}': {e}")
            cache[key] = (status, candidate)

        counters[status] = counters.get(status, 0) + 1

        results.append({
            "job_offer_id": offer_id,
            "employer_name_on_offer": name,
            "offer_commune_code": commune_code,
            "offer_naf_code": naf_code,
            "match_status": status,
            "company": extract_fields(candidate) if candidate else None,
        })

        print(f"[{i}/{len(offers)}] {name} -> {status}")

    total_matches = sum(n for s, n in counters.items() if s.startswith("match"))
    rate = 100 * total_matches / len(offers)

    # {metadata, resultats} structure, identical to the France Travail
    # ingestion dump: consistency across raw sources.
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    output_path = f"{OUTPUT_DIR}/enrich_dinum_{timestamp}.json"

    output = {
        "metadata": {
            "execution_date": datetime.now().isoformat(),
            "source": "Company Search API (DINUM)",
            "endpoint": DINUM_URL,
            "target_population": "fct_job_offer where employer_category = 'DIRECT_EMPLOYER'",
            "offer_count": len(offers),
            "unique_call_count": len(cache),
            "match_count": total_matches,
            "matching_rate_pct": round(rate, 1),
            "status_breakdown": counters,
        },
        "resultats": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print_quality_audit(results, total_matches)

    print("\n--- Status breakdown ---")
    for status, n in sorted(counters.items(), key=lambda x: -x[1]):
        print(f"  {status}: {n} ({100 * n / len(offers):.1f}%)")

    print(f"\nMATCHING RATE: {total_matches}/{len(offers)} ({rate:.1f}%)")
    print(f"API calls saved by the cache: {len(offers) - len(cache)}")
    print(f"\nDump written: {output_path}")


if __name__ == "__main__":
    # No option today, but argparse still rejects an unknown or mistyped
    # argument instead of silently ignoring it while a real dump gets
    # written and picked up by dbt.
    parser = argparse.ArgumentParser(
        description="Enrich DIRECT_EMPLOYER offers with SIRENE data (DINUM API).",
        allow_abbrev=False,
    )
    parser.parse_args()
    main()
