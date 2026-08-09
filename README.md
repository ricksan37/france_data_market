# Observatoire du Marché Data France

Pipeline analytique qui ingère les offres d'emploi data du marché français depuis l'API **France Travail**, les transforme via **dbt** et **DuckDB**, et les enrichit avec les données d'entreprise du répertoire SIRENE et une extraction de compétences par LLM local.

Projet de portfolio pour une transition vers l'**Analytics Engineering**. L'accent est mis sur une chaîne **claire, traçable et honnête sur ses limites** — plus que sur le volume : chaque choix (périmètre, dédoublonnage, matching, modèle LLM) est justifié par une mesure, pas par une intuition, et documenté comme tel.

> **Statut** — Phases 1 à 4 terminées. Phase 5 (automatisation) opérationnelle : cron hebdomadaire actif chaque lundi. Phase 6a (restitution) livrée : rapport HTML statique, régénéré à chaque run.

---

## Quatre décisions qui illustrent la méthode

### Taux de matching entreprise : 19,2 % → 80,3 %

Le premier essai d'enrichissement (nom + code postal) ne matchait qu'une offre sur cinq. Onze paliers de diagnostic plus tard — chacun déclenché par une mesure sur données réelles, jamais une intuition — le taux atteint 80,3 % sur les 213 offres concernées. Deux règles qui *fonctionnaient* ont même été supprimées en cours de route parce qu'elles produisaient des faux positifs : le taux a gagné en fiabilité plus qu'en volume.

### La spec disait code postal. Les données disaient code INSEE.

La spécification initiale prévoyait le code postal comme clé de jointure géographique pour l'enrichissement entreprise. Mesure sur les 213 offres cibles : le code postal couvre 166 offres, le code INSEE en couvre 198 — un sur-ensemble strict, jamais absent quand le code postal l'est. Plutôt que de suivre le plan initial ou de dévier silencieusement, la spécification a été rouverte et réécrite avec la mesure comme justification (§7.5, v2.0 → v2.1). Un gain de +19 % de couverture, documenté plutôt que découvert plus tard.

### Trois modèles LLM locaux, comparés à l'aveugle sur une tâche réelle

Pour extraire les compétences techniques du texte libre des annonces, trois modèles ont tourné en local (Ollama) sur le même prompt et la même offre de référence : Mistral 7B, Qwen3 8B et Mistral-Nemo 12B. Résultat inattendu — la vitesse et la qualité n'étaient pas liées à la taille de façon simple : Qwen3 en mode "thinking" mettait 258 s/offre pour un gain de qualité marginal ; désactiver ce mode l'a rendu 23× plus rapide *sans perte de qualité*. Seul Nemo distinguait de façon fiable un produit nommé (Azure, Databricks) d'un concept technique (RAG, CI/CD) — un défaut que trois reformulations de prompt n'ont pas réussi à corriger sur les deux modèles plus petits. Le modèle a été choisi sur cette mesure, pas sur sa réputation.

### Une source figée sur un nom de fichier, invisible jusqu'au premier run automatisé

`_sources.yml` pointait sur un dump JSON nommé explicitement (`offres_2026-07-17_1403.json`). En usage manuel, ça ne posait jamais problème : c'était moi qui décidais quand relancer l'ingestion, et je savais qu'il fallait mettre le nom à jour. Automatiser le pull hebdomadaire (GitHub Actions) a exposé ce couplage silencieux : sans intervention, le pipeline aurait reconstruit indéfiniment le même jeu de 552 offres du 17 juillet, quel que soit ce que l'ingestion venait de ramener. Corrigé en passant à un motif (`offres_*.json`) plutôt qu'un nom figé — sans toucher à la règle de dédoublonnage déjà en place (`qualify row_number()... order by date_actualisation desc`, Session 1), qui gérait déjà, par construction, le cas de plusieurs dumps qui se chevauchent, avant même que le besoin existe. Un bug qui n'existait que dans un scénario d'exécution non supervisée — visible uniquement lors d'un run automatisé réel, pas à la relecture du code.

---

## Restitution : un rapport qui dégrade proprement, jamais silencieusement
 
Le rapport HTML (`dashboard/rapport.html`, régénéré à chaque run dbt) a été tranché contre Streamlit et une SPA React : un fichier statique auto-contenu correspond à l'usage réel (portfolio consultable sans setup) et se construit plus simplement en HTML/CSS natif qu'en la forçant dans un framework qui a son propre système de thème.
 
**Limite assumée, pas cachée** : l'extraction LLM (Ollama, ~5h en local) ne tourne jamais sur le runner GitHub Actions. Deux sections du rapport (Skills Demand, Domaines) dépendent de cette extraction et sont donc **systématiquement
vides sur tout rapport généré automatiquement** — le pipeline le détecte (résultat de requête vide plutôt qu'une variable d'environnement relue en aval, plus robuste) et affiche un message explicite au lieu d'un graphique cassé ou d'une erreur silencieuse. Ces deux sections sont volontairement placées en fin de rapport plutôt qu'en tête, pour que le rapport généré en CI (le cas le plus fréquent) s'ouvre sur des sections toujours peuplées. Le rapport complet, avec ces deux sections remplies, s'obtient uniquement en le générant en local après un run de `extraction_skills.py`.

---

## Objectif

Constituer un jeu de données propre et reproductible sur le marché de l'emploi data en France, pour répondre à des questions comme : quels métiers recrutent le plus, quelles technologies sont demandées, quelle répartition géographique, quels employeurs recrutent réellement derrière les intermédiaires.

## Principe directeur : *raw jamais modifié*

Les offres extraites de l'API — et, de la même façon, les résultats d'enrichissement et d'extraction LLM — sont déposés **tels quels** dans `data/raw/`. Aucun filtrage, aucun dédoublonnage n'est appliqué côté Python. Toute transformation relève de la couche **dbt** en aval. Ce découplage garantit qu'on peut rejouer et auditer les transformations sans jamais re-solliciter les API sources.

## Stratégie de périmètre : hybride `codeROME` / `motsCles`

L'exploration du référentiel ROME (cf. `exploration/`) a montré que les métiers data ne se laissent pas capturer par une seule méthode :

| Méthode | Quand | Exemples |
|---|---|---|
| `codeROME` entier | métier ROME dédié à la data | M1405 (Data scientist), M1811 (Data engineer) |
| `motsCles` ciblé | intitulé isolé dans un code ROME fourre-tout | « data analyst », « data architect », « décisionnel », « business intelligence » |

Les codes fourre-tout (M1403, M1805, M1806, M1868) mélangent la data avec des dizaines de métiers sans rapport : les prendre en entier polluerait le jeu de données, d'où le recours au filtrage par mot-clé pour ces cas.

**Limite assumée** : le tag ROME n'est pas parfaitement fiable même sur les codes dédiés — l'API classe parfois des offres hors périmètre data sous ces codes (ex. « Chargé qualité produit sous-traitance » taggé M1811). Le pipeline ne filtre pas ces cas a posteriori ; ils restent visibles et mesurables dans les résultats plutôt que masqués par une règle de nettoyage construite sur peu d'exemples.

## Architecture

```
API France Travail ──► pull_complet.py ──► data/raw/offres_*.json ─┐
                                                                     │
API DINUM ──► enrichissement_dinum.py ──► data/raw/enrich_*.json ──┤
                                                                     │
LLM local (Ollama) ──► extraction_skills.py ──► data/raw/skills_*.json ─┤
                                                                     ▼
                                                              sources dbt
                                                                     │
                                                                staging
                                                                     │
                                                              intermediate
                                                                     │
                                                                  marts
```

dbt ne fait ni appel HTTP ni appel LLM. Chaque enrichissement suit le même pattern : script Python autonome → dump JSON horodaté dans `data/raw/` → source dbt → modèle `stg_`. Le cycle apparent (les scripts d'enrichissement lisent `fct_offre` en amont) est résolu par le séquencement des exécutions (`dbt run` → script → `dbt run`), pas par une dépendance circulaire réelle.

### Couches dbt

- **staging** (`stg_`) — renommage, casting, dédoublonnage. Aucune logique métier.
- **intermediate** (`int_`) — parsing salaire, classification employeur. Logique métier isolée et testée unitairement.
- **marts** — tables exposées : `fct_offre` (grain fin, une ligne = une offre), `dim_rome`, `dim_commune`, `dim_entreprise`, `fct_offre_technologie`, `fct_offre_domaine`.

## Automatisation (Phase 5)

Un workflow GitHub Actions (`.github/workflows/pull_hebdo.yml`) reproduit la chaîne complète chaque lundi à 6h UTC (et sur déclenchement manuel) : ingestion → `dbt build` → snapshot. Le seul artefact qui persiste d'un run à l'autre est `data/snapshots/marche_hebdo.csv` — le runner GitHub est une machine jetable, `warehouse.duckdb` et les dumps JSON hebdomadaires restent éphémères, exactement comme en local.

**Une contrainte réelle a forcé une décision d'architecture.** L'extraction de compétences (Ollama, ~3h/552 offres) ne peut pas tourner sur un runner CI. Or `fct_offre` et `int_classification_employeur` dépendent de cette extraction depuis la reclassification `INTERMEDIAIRE_reclasse`. Plutôt que de casser le build en CI, une variable d'environnement (`CI_SANS_EXTRACTION`) fait dégrader `stg_offres_skills` en 0 ligne (même schéma) quand le dump n'existe pas — le `left join` déjà en place absorbe le cas sans modification de logique, vérifié dans les deux sens :

| Mode | ANONYME | INTERMEDIAIRE_reclasse |
|---|---:|---:|
| Local (extraction disponible) | 187 | 21 |
| CI (extraction absente) | 208 | 0 |

Assumé et documenté plutôt que masqué : le snapshot automatique n'inclut jamais `top_technologie` ni la reclassification texte — ces deux métriques restent réservées à un run manuel en local, après une extraction Ollama à jour.

## Structure du projet

```
marche_data/
├── auth.py, search.py, pull_complet.py       # Ingestion France Travail (Phase 1)
├── enrichissement_dinum.py                    # Enrichissement SIRENE/DINUM (Phase 3)
├── extraction_skills.py                       # Extraction LLM (Phase 4)
├── snapshot_hebdo.py                           # Snapshot hebdomadaire (Phase 5)
├── requirements.txt
├── .github/
│   └── workflows/
│       └── pull_hebdo.yml                      # Cron hebdo + déclenchement manuel (Phase 5)
├── data/
│   ├── raw/                                   # Dumps JSON horodatés, source de vérité brute
│   ├── snapshots/
│   │   └── marche_hebdo.csv                    # Historique hebdo, seul artefact persisté par la CI
│   └── warehouse.duckdb                       # Base DuckDB, régénérable, gitignorée
├── exploration/                                # Scripts de diagnostic, conservés comme trace de décision
│   ├── check_codeROME.py, check_rome.py, get_referentiel.py   # Cadrage du périmètre (Phase 1)
│   ├── diag_*.py                               # Diagnostics de matching (Phase 3)
│   ├── test_extraction_*.py, schema_extraction.py             # Comparaison de modèles LLM (Phase 4)
│   └── check_classification.py                 # Contrôle qualité post-run
├── docs/                                       # Spec + comptes rendus de session, journal de bord
└── observatoire/                               # Projet dbt
    ├── macros/
    │   └── environnement_ci.sql                # Drapeau CI_SANS_EXTRACTION (Phase 5)
    ├── models/
    │   ├── staging/       # stg_
    │   ├── intermediate/  # int_
    │   └── marts/         # dim_, fct_
    └── tests/              # Tests singuliers, garde-fous documentés
```

## Installation

```bash
git clone <repo>
cd marche_data
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Créer un fichier `.env` à la racine (jamais commité, cf. `.gitignore`) avec les identifiants obtenus sur l'espace partenaire France Travail :

```
FT_CLIENT_ID=xxxxxxxx
FT_CLIENT_SECRET=xxxxxxxx
```

Aucune clé API n'est requise pour reproduire la couche dbt : `profiles.yml` est versionné, DuckDB ne demande aucun credential, et l'extraction de compétences tourne sur un modèle local (Ollama, gratuit).

```bash
cd observatoire
dbt debug
dbt run
dbt test
```

## Utilisation

```bash
# Ingestion (Phase 1) — produit data/raw/offres_<horodatage>.json
python3 pull_complet.py

# Enrichissement SIRENE/DINUM (Phase 3) — nécessite dbt run préalable (lit fct_offre)
python3 enrichissement_dinum.py

# Extraction de compétences (Phase 4) — nécessite Ollama + mistral-nemo, ~3h/552 offres
ollama pull mistral-nemo
python3 extraction_skills.py

# Snapshot hebdomadaire (Phase 5) — calcule 8 métriques et les ajoute à
# data/snapshots/marche_hebdo.csv. Automatisé via GitHub Actions (cron
# lundi 6h UTC) ; peut aussi être lancé manuellement.
python3 snapshot_hebdo.py
```

Chaque exécution produit un fichier horodaté distinct : rien n'est écrasé, l'historique des runs est conservé.

## Anatomie des fichiers produits

Les trois scripts (ingestion, enrichissement, extraction) produisent la même structure `{metadata, resultats}` — traçabilité de l'exécution, pas seulement des données :

```json
{
  "metadata": {
    "date_execution": "...",
    "population_cible": "...",
    "nb_offres": 0,
    "...": "mesures spécifiques à chaque étape (taux de matching, répartition de statuts...)"
  },
  "resultats": [ /* données brutes, non modifiées */ ]
}
```

## Exemple de run — ingestion (17/07/2026)

| Catégorie | Filtre | Offres |
|---|---|---:|
| Data scientist | `codeROME=M1405` | 125 |
| Data engineer | `codeROME=M1811` | 450 |
| Data analyst | `motsCles=data analyst` | 300 |
| Data architect | `motsCles=data architect` | 45 |
| Décisionnel | `motsCles=décisionnel` | 85 |
| Business Intelligence | `motsCles=business intelligence` | 89 |
| **Total brut** | | **1 094** |
| **ID uniques** | | **552** |

L'écart entre offres brutes (1 094) et ID uniques (552) est **attendu** : une même offre peut matcher plusieurs mots-clés ou codes ROME. Le dédoublonnage est traité en aval par dbt (`stg_ft_offres`), pas à l'ingestion.

---

## Stack

| Composant | Version | Pourquoi |
|---|---|---|
| dbt-core | 1.11.7 | |
| dbt-duckdb | 1.10.1 | |
| DuckDB | 1.5.4 | OLAP colonnaire in-process, zero-copy Arrow/Pandas. Le pipeline s'exécute en quelques secondes sur une machine locale, sans serveur ni infrastructure à provisionner. |
| Ollama + Mistral-Nemo 12B | | Extraction de compétences structurées, en local. Coût nul, aucune clé API requise pour reproduire le pipeline. |
| GitHub Actions | | Automatisation du pull hebdomadaire. Runner jetable : seul le snapshot agrégé persiste entre deux runs. |
| Python | 3.13 | requests, python-dotenv, duckdb, pydantic, ollama |

**Réserve assumée** : DuckDB 1.5.4 porte un bug connu de l'optimiseur sur `IN()`/`NOT IN()` à plusieurs valeurs à l'intérieur d'une vue interrogée (`INTERNAL Error: Attempted to access index...`). Contournement systématique : conditions `=`/`!=` chaînées par `OR`/`AND`, appliqué à tout le code SQL du projet. Le coût est réel ; il est documenté ici plutôt que dissimulé.

---

## Roadmap

- [x] **Phase 1 — Ingestion** — API France Travail, OAuth2, dédoublonnage. 552 offres uniques (dump de référence).
- [x] **Phase 2 — Socle dbt** — staging, intermediate, marts, tests. `fct_offre` exposée et testée.
- [x] **Phase 3 — Enrichissement** — matching SIRENE/DINUM (80,3 %), `dim_entreprise`.
- [x] **Phase 4 — Extraction skills** — schéma d'extraction structuré, comparaison de modèles, `fct_offre_technologie` / `fct_offre_domaine`. Reclassification `INTERMEDIAIRE_reclasse` (21 offres, texte libre) en aval.
- [ ] **Phase 5 — Snapshot & historique** (en cours) — GitHub Actions opérationnel (cron hebdo + déclenchement manuel), dégradation CI sans LLM vérifiée dans les deux sens, premier run réel réussi. `fct_marche_hebdo` (mart dbt exposant l'historique) pas encore construit — en attente de plusieurs semaines de snapshots pour être utile.
- [ ] **Phase 6 — Restitution** — dashboard, tests de qualité continus (Elementary).

---

## Limites connues et assumées

Un projet honnête documente ce qu'il ne sait pas résoudre plutôt que de le cacher.

- **Plafond API France Travail** : 1 150 résultats par recherche (pagination `Range` 0–1149). Au-delà, il faudrait affiner (ex. par date). Hors scope pour l'instant.
- **Index temps réel** : la pagination s'effectue sur un index vivant, d'où des doublons possibles au sein d'une même catégorie — mesurés, non corrigés à l'ingestion (dédoublonnage différé à `stg_ft_offres`, par design).
- **EY non matché** (28 offres, 13 %) — sigle commercial absent du répertoire SIRENE, aucun critère fiable pour départager les 5+ entités juridiques du groupe. Non matché volontairement plutôt que par une règle arbitraire.
- **Consolidation groupe sur homonymes** (27 cas) — les filiales portant un nom identique à leur maison mère sont rattachées à la plus grande structure (`nombre_etablissements` maximal), un choix justifié par l'objectif analytique (caractériser le type de structure qui recrute), pas une approximation cachée. Statut distinct en base pour filtrer ce comportement si besoin.
- **Extraction LLM sur le champ `domaines`** — le modèle retenu (Mistral-Nemo) sous-extrait ce champ sur les annonces de conseil en stratégie, au bénéfice d'une bien meilleure fiabilité sur le champ `technologies`, jugé prioritaire pour l'objectif du projet.
- **Bornes de plausibilité salariale** — établies uniquement pour les salaires annuels (152 offres mesurées). Les salaires horaires et mensuels (19 et 1 offres respectivement) sont trop peu nombreux pour fonder une règle statistique défendable ; la question reste différée tant que l'échantillon ne grossit pas (revérifié sans changement en Session 7).
- **Snapshot automatisé sans extraction LLM** — le runner GitHub Actions ne peut pas exécuter Ollama (~3h/552 offres). Le snapshot hebdomadaire produit par le cron ne comporte donc jamais `top_technologie` ni la reclassification `INTERMEDIAIRE_reclasse` (valeurs marquées explicitement "non disponible (CI)" plutôt que silencieusement fausses ou absentes). Ces deux métriques restent disponibles uniquement après un run manuel en local, extraction Ollama à jour.

## Suite prévue

- **Phase 5** : `fct_marche_hebdo`, une fois l'historique de snapshots suffisant pour en tirer des comparaisons semaine sur semaine.
- **Phase 6** : dashboard, tests de qualité continus (Elementary — a besoin de cet historique pour détecter des dérives), README enrichi des enseignements finaux.