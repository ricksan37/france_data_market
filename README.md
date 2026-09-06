# Observatoire du Marché Data France

Pipeline analytique qui ingère les offres d'emploi data du marché français depuis l'API **France Travail**, les transforme via **dbt** et **DuckDB**, et les enrichit avec les données d'entreprise du répertoire SIRENE et une extraction de compétences par LLM local.

Projet de portfolio pour une transition vers l'**Analytics Engineering**. L'accent est mis sur une chaîne **claire, traçable et honnête sur ses limites**, plus que sur le volume : chaque choix (périmètre, dédoublonnage, matching, modèle LLM) est justifié par une mesure, pas par une intuition, et documenté comme tel.

> **Statut** : Phases 1 à 5 terminées. Cron hebdomadaire actif chaque lundi, CI sur chaque poussée, quatre semaines d'historique de corpus et trois points de flux. Phase 6 en cours : rapport HTML statique livré, README et notebook d'exploration à jour, dashboard interactif restant.

---

## Huit décisions qui illustrent la méthode

### Taux de matching entreprise : 19,2 % → 80,3 %

Le premier essai d'enrichissement (nom + code postal) ne matchait qu'une offre sur cinq. Onze paliers de diagnostic plus tard (chacun déclenché par une mesure sur données réelles, jamais une intuition), le taux atteint 80,3 % sur les 213 offres concernées. Deux règles qui *fonctionnaient* ont même été supprimées en cours de route parce qu'elles produisaient des faux positifs : le taux a gagné en fiabilité plus qu'en volume.

### La spec disait code postal. Les données disaient code INSEE.

La spécification initiale prévoyait le code postal comme clé de jointure géographique pour l'enrichissement entreprise. Mesure sur les 213 offres cibles : le code postal couvre 166 offres, le code INSEE en couvre 198, un sur-ensemble strict, jamais absent quand le code postal l'est. Plutôt que de suivre le plan initial ou de dévier silencieusement, la spécification a été rouverte et réécrite avec la mesure comme justification (§7.5, v2.0 → v2.1). Un gain de +19 % de couverture, documenté plutôt que découvert plus tard.

**Et je ne l'avais appliqué qu'à moitié.** La correction avait été portée sur l'enrichissement entreprise, jamais sur la dimension géographique, restée indexée sur le seul code postal. Or Paris, Lyon et Marseille sont les trois communes françaises à arrondissements : elles n'ont pas de code postal unique, donc la source renvoie leur code INSEE de commune globale avec un code postal vide. Mesure du 04/09 : 95 offres dans ce cas, dont 77 à Paris. Le rapport affichait 74 offres parisiennes là où il y en a 151, et faisait passer Paris pour deux fois Lyon quand le rapport réel est de 3,3. Une clé unifiée `coalesce(code_postal, code_insee)` porte la couverture de 79 % à 89 % du corpus. La leçon de la première fois n'était pas « corriger cette jointure-ci », c'était « la clé géographique de cette source n'est pas le code postal », et je ne l'avais tirée que localement.

### Trois modèles LLM locaux, comparés à l'aveugle sur une tâche réelle

Pour extraire les compétences techniques du texte libre des annonces, trois modèles ont tourné en local (Ollama) sur le même prompt et la même offre de référence : Mistral 7B, Qwen3 8B et Mistral-Nemo 12B. Résultat inattendu : la vitesse et la qualité n'étaient pas liées à la taille de façon simple : Qwen3 en mode "thinking" mettait 258 s/offre pour un gain de qualité marginal ; désactiver ce mode l'a rendu 23× plus rapide *sans perte de qualité*. Seul Nemo distinguait de façon fiable un produit nommé (Azure, Databricks) d'un concept technique (RAG, CI/CD), un défaut que trois reformulations de prompt n'ont pas réussi à corriger sur les deux modèles plus petits. Le modèle a été choisi sur cette mesure, pas sur sa réputation.

### Une source figée sur un nom de fichier, invisible jusqu'au premier run automatisé

`_sources.yml` pointait sur un dump JSON nommé explicitement (`offres_2026-07-17_1403.json`). En usage manuel, ça ne posait jamais problème : c'était moi qui décidais quand relancer l'ingestion, et je savais qu'il fallait mettre le nom à jour. Automatiser le pull hebdomadaire (GitHub Actions) a exposé ce couplage silencieux : sans intervention, le pipeline aurait reconstruit indéfiniment le même jeu de 552 offres du 17 juillet, quel que soit ce que l'ingestion venait de ramener. Corrigé en passant à un motif (`offres_*.json`) plutôt qu'un nom figé, sans toucher à la règle de dédoublonnage déjà en place (`qualify row_number()... order by date_actualisation desc`), qui gérait déjà, par construction, le cas de plusieurs dumps qui se chevauchent, avant même que le besoin existe. Un bug qui n'existait que dans un scénario d'exécution non supervisée, visible uniquement lors d'un run automatisé réel, pas à la relecture du code.

### Ma propre table de faits mesurait la mauvaise chose

`fct_offre` unionne tous les dumps collectés et les dédoublonne. C'est le bon comportement pour un corpus, et le mauvais pour une mesure de marché : une offre vue une fois y reste pour toujours. Mesure du 31/08 : sur les 552 offres de juillet, **463 avaient disparu de France Travail six semaines plus tard**, soit 83,9 %, et le corpus les comptait encore. Une courbe du nombre d'offres tirée de cette table raconte la taille de mon fichier, pas l'état du marché.

D'où deux tables de faits au lieu d'une, chacune avec sa portée écrite en tête du modèle. `fct_marche_hebdo` mesure le corpus accumulé. `fct_marche_flux` mesure la présence réelle des offres dans chaque collecte, et c'est la seule qui sait dire ce qui apparaît et ce qui disparaît. Elle s'appuie sur un historique au grain de l'offre (`data/snapshots/presence_offres.csv`), un couple (semaine, offre_id) par observation, qui préserve les réapparitions et permet de calculer une survie par cohorte, là où un simple couple première vue / dernière vue les aurait écrasées.

Le test qui garde l'ensemble honnête relie trois mesures calculées indépendamment : les offres actives d'une semaine doivent être celles de la semaine précédente, moins les sorties, plus les nouvelles. `552 - 463 + 408 = 497`. Si l'une des trois dérive, l'égalité casse.

### Invisible sur l'agrégat, destructrice sur la tranche

Quinze offres sur 275 portent un salaire annuel implausible : onze à 1 800 €, quatre entre 15 et 40 €. Sur la médiane globale, elles ne changent **rien** : 45 000 € avec ou sans elles, parce que quinze valeurs sur 275 ne déplacent pas une médiane. Sur une tranche, elles la retournent. La médiane des offres mentionnant Tableau affichait **1 800 € au lieu de 37 000 €**, celle d'Excel 1 800 au lieu de 35 000. Ces deux outils sont associés aux profils juniors, donc ils concentraient les annonces au salaire mensuel mal étiqueté.

Pire : les onze annonces à 1 800 € étaient toutes classées `ANONYME`. À elles seules, elles créaient un écart salarial apparent de 5 000 € entre employeurs masqués et employeurs directs. Une fois écartées, les trois catégories tombent exactement sur la même médiane, 45 000 €. Ce qui sépare vraiment les catégories n'est pas le salaire, c'est le fait de l'afficher : 53,9 % chez les intermédiaires nommés contre 12,7 % chez les employeurs masqués.

La tentation était de corriger la période, d'autant qu'une mesure antérieure avait déjà reclassé « Mensuel > 10 000 € » en annuel sur une zone vide de la distribution, et que la figure symétrique existe ici (rien entre 1 800 et 25 000 €). Mesure du coût avant de céder : reclasser porterait 24 % de la population mensuelle à un seul annonceur, doublerait la population horaire avec la moitié de valeurs nouvelles, et **ne changerait rien à l'annuel**. On abîmerait deux petites populations pour ne rien gagner sur la grande. Un drapeau `salaire_annuel_plausible` exclut donc sans détruire, protégé par un test en `severity: error`.

### Compter des offres ou compter des annonces

Le dédoublonnage de `stg_ft_offres` travaille sur `offre_id` : il écarte les doublons d'index de l'API, pas les campagnes. Or un même poste publié dans plusieurs villes reçoit un identifiant par ville. Mesure : **152 offres sur 960, soit 15,8 % du corpus, partagent leur texte avec au moins une autre**. La plus grosse grappe est un employeur publiant la même annonce dans 24 communes sur sept semaines.

Deux classements de tête s'inversent une fois les campagnes neutralisées. **Python (262) passe devant SQL (235)** alors que les deux semblaient au coude-à-coude, 283 contre 282 : SQL est la compétence la plus générique, donc la plus présente dans les textes standardisés qu'on republie tels quels. Et **l'Analyse de données passe devant la Gouvernance des données**, parce que la plus grosse campagne du corpus était justement un poste de Data Governance Manager.

La signature est l'empreinte du texte normalisé, sans aucun seuil de similarité : deux textes sont identiques ou ils ne le sont pas. Un seuil attraperait davantage (sur onze annonces d'une même campagne, neuf partagent exactement le même texte), mais rien ne permet aujourd'hui d'en défendre un.

Aucune offre n'est supprimée. Trois colonnes exposent le choix, et chaque mesure du rapport déclare lequel elle fait : les technologies, les domaines et les salaires se comptent en annonces, la géographie en offres, parce qu'un poste ouvert dans vingt-quatre communes représente une opportunité dans chacune. L'exception est signalée sous le graphique concerné, jamais implicite.

### Le Slim CI optimisait un coût qui n'existait pas

La spécification prévoyait un build incrémental en Phase 6 : `dbt build --select state:modified+ --defer`, pour ne reconstruire que ce qui a changé. Mesure avant de l'écrire : **le build complet prend 1,79 seconde**, quinze modèles, trente-neuf tests et deux unit tests compris. Il n'y a rien à économiser. Et `--defer` suppose un environnement de production persistant vers lequel différer les modèles non reconstruits, quand `warehouse.duckdb` est éphémère sur un runner jetable. Le mécanisme est donc à la fois inutile et inapplicable ici.

La vérification a trouvé autre chose : **il n'y avait aucune intégration continue sur ce dépôt**. Le seul workflow se déclenchait le lundi ou à la main. Un modèle qui ne compile pas partait sur `main` et n'était découvert qu'au run hebdomadaire suivant. Le besoin réel n'était pas d'optimiser une CI, c'était d'en avoir une.

Elle vérifie par ailleurs une affirmation que ce README fait depuis la Phase 2 sans que rien ne la contrôle : le dump France Travail de référence, le dump SIRENE et les deux CSV de snapshot étant versionnés, **le graphe entier se reconstruit sur les seules données du dépôt, sans aucune clé d'API**. Ce qu'obtient la CI est ce qu'obtient un tiers qui clone le projet.

---

## Restitution : un rapport qui dégrade proprement, jamais silencieusement
 
Les trois polices de l'identité sont **embarquées en base64** (50 Ko après sous-ensemblage au latin, cf. `dashboard/preparer_polices.py`). Le rapport déclarait auparavant des polices système pour rester autonome ; mesuré le 31/08, rendu sur une machine dépourvue d'Arial Black, les titres de graphiques perdaient leurs accents. Un livrable de portfolio ne peut pas dépendre de ce qui est installé chez celui qui l'ouvre. L'embarquement tient les deux exigences à la fois.

Le rapport HTML (`dashboard/rapport.html`, régénéré à chaque run dbt) a été tranché contre Streamlit et une SPA React : un fichier statique auto-contenu correspond à l'usage réel (portfolio consultable sans setup) et se construit plus simplement en HTML/CSS natif qu'en la forçant dans un framework qui a son propre système de thème.
 
**Limite assumée, pas cachée** : l'extraction LLM (Ollama, ~5h en local) ne tourne jamais sur le runner GitHub Actions. Deux sections du rapport (Skills Demand, Domaines) dépendent de cette extraction et sont donc **systématiquement
vides sur tout rapport généré automatiquement** : le pipeline le détecte (résultat de requête vide plutôt qu'une variable d'environnement relue en aval, plus robuste) et affiche un message explicite au lieu d'un graphique cassé ou d'une erreur silencieuse. Ces deux sections sont volontairement placées en fin de rapport plutôt qu'en tête, pour que le rapport généré en CI (le cas le plus fréquent) s'ouvre sur des sections toujours peuplées. Le rapport complet, avec ces deux sections remplies, s'obtient uniquement en le générant en local après un run de `extraction_skills.py`.

---

## Objectif

Constituer un jeu de données propre et reproductible sur le marché de l'emploi data en France, pour répondre à des questions comme : quels métiers recrutent le plus, quelles technologies sont demandées, quelle répartition géographique, quels employeurs recrutent réellement derrière les intermédiaires.

## Principe directeur : *raw jamais modifié*

Les offres extraites de l'API, et de la même façon les résultats d'enrichissement et d'extraction LLM, sont déposés **tels quels** dans `data/raw/`. Aucun filtrage, aucun dédoublonnage n'est appliqué côté Python. Toute transformation relève de la couche **dbt** en aval. Ce découplage garantit qu'on peut rejouer et auditer les transformations sans jamais re-solliciter les API sources.

## Stratégie de périmètre : hybride `codeROME` / `motsCles`

L'exploration du référentiel ROME (cf. `exploration/`) a montré que les métiers data ne se laissent pas capturer par une seule méthode :

| Méthode | Quand | Exemples |
|---|---|---|
| `codeROME` entier | métier ROME dédié à la data | M1405 (Data scientist), M1811 (Data engineer) |
| `motsCles` ciblé | intitulé isolé dans un code ROME fourre-tout | « data analyst », « data architect », « décisionnel », « business intelligence » |

Les codes fourre-tout (M1403, M1805, M1806, M1868) mélangent la data avec des dizaines de métiers sans rapport : les prendre en entier polluerait le jeu de données, d'où le recours au filtrage par mot-clé pour ces cas.

**Limite assumée** : le tag ROME n'est pas parfaitement fiable même sur les codes dédiés : l'API classe parfois des offres hors périmètre data sous ces codes (ex. « Chargé qualité produit sous-traitance » taggé M1811). Le pipeline ne filtre pas ces cas a posteriori ; ils restent visibles et mesurables dans les résultats plutôt que masqués par une règle de nettoyage construite sur peu d'exemples.

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

- **staging** (`stg_`) : renommage, casting, dédoublonnage. Aucune logique métier.
- **intermediate** (`int_`) : parsing salaire, plausibilité des montants, classification employeur, regroupement des annonces identiques. Logique métier isolée et testée unitairement.
- **marts** : tables exposées : `fct_offre` (grain fin, une ligne = une offre), `dim_rome`, `dim_commune`, `dim_entreprise`, `fct_offre_technologie`, `fct_offre_domaine`, `fct_marche_hebdo` (une ligne par semaine, corpus accumulé) et `fct_marche_flux` (une ligne par semaine, flux réel du marché).

## Intégration continue

Deux workflows, deux rôles distincts.

`.github/workflows/ci.yml` se déclenche à **chaque poussée et chaque pull request**. Il compile les 34 scripts Python, reconstruit le graphe dbt entier avec ses tests, et génère le rapport. **Aucun secret n'est nécessaire** : le dump France Travail de référence, le dump SIRENE et les deux CSV de snapshot sont versionnés, donc le pipeline se rebâtit sur les seules données du dépôt. La CI vérifie ainsi à chaque commit ce que la section Installation promet.

`.github/workflows/pull_hebdo.yml` se déclenche **le lundi**. Lui produit de la donnée : ingestion, historique de présence, build, snapshot, rapport, commit. Les deux ne se recouvrent pas : l'un valide du code, l'autre rafraîchit des faits.

## Automatisation (Phase 5)

Un workflow GitHub Actions (`.github/workflows/pull_hebdo.yml`) reproduit la chaîne complète chaque lundi à 6h UTC (et sur déclenchement manuel) : ingestion → `dbt build` → snapshot. Le seul artefact qui persiste d'un run à l'autre est `data/snapshots/marche_hebdo.csv` : le runner GitHub est une machine jetable, `warehouse.duckdb` et les dumps JSON hebdomadaires restent éphémères, exactement comme en local.

**Une contrainte réelle a forcé une décision d'architecture.** L'extraction de compétences (Ollama, ~28 s par offre en local) ne peut pas tourner sur un runner CI. Or `fct_offre` et `int_classification_employeur` dépendent de cette extraction depuis la reclassification `INTERMEDIAIRE_reclasse`. Plutôt que de casser le build en CI, une variable d'environnement (`CI_SANS_EXTRACTION`) fait dégrader `stg_offres_skills` en 0 ligne (même schéma) quand le dump n'existe pas, le `left join` déjà en place absorbe le cas sans modification de logique, vérifié dans les deux sens :

| Mode | ANONYME | INTERMEDIAIRE_reclasse |
|---|---:|---:|
| Local, extraction disponible | 323 | 33 |
| CI, extraction absente | 357 | *(vide)* |

La cellule est **vide et non nulle** en CI. Un zéro se lit comme une mesure : il ferait passer une donnée indisponible pour une reclassification qui n'aurait rien trouvé, et une courbe 33 → 0 se lirait comme un effondrement. Correctif validé en production sur le run du 31/08.

Assumé et documenté plutôt que masqué : le snapshot automatique n'inclut jamais `top_technologie` ni la reclassification texte, ces deux métriques restent réservées à un run manuel en local, après une extraction Ollama à jour.

Le workflow écrit deux fichiers, jamais en ajout : `marche_hebdo.csv` en upsert sur la semaine ISO, `presence_offres.csv` en upsert sur le couple (semaine, offre). Un déclenchement manuel en cours de semaine met donc la ligne à jour au lieu de la dupliquer : l'ancienne écriture en ajout avait produit trois lignes pour une même semaine, et un grain cassé pour toute table construite dessus.

## Structure du projet

```
marche_data/
├── auth.py, search.py, pull_complet.py       # Ingestion France Travail (Phase 1)
├── enrichissement_dinum.py                    # Enrichissement SIRENE/DINUM (Phase 3)
├── extraction_skills.py                       # Extraction LLM (Phase 4), reprise incrémentale
├── snapshot_hebdo.py                           # Snapshot du corpus, une ligne par semaine (Phase 5)
├── presence_offres.py                          # Historique au grain de l'offre (Phase 5)
├── requirements.txt
├── .github/
│   └── workflows/
│       └── pull_hebdo.yml                      # Cron hebdo + déclenchement manuel (Phase 5)
├── data/
│   ├── raw/                                   # Dumps JSON horodatés, source de vérité brute
│   ├── snapshots/                             # Seuls artefacts persistés par la CI
│   │   ├── marche_hebdo.csv                    # Une ligne par semaine, corpus
│   │   └── presence_offres.csv                 # Un couple (semaine, offre) par observation
│   └── warehouse.duckdb                       # Base DuckDB, régénérable, gitignorée
├── exploration/                                # Scripts de diagnostic, conservés comme trace de décision
│   ├── check_codeROME.py, check_rome.py, get_referentiel.py   # Cadrage du périmètre (Phase 1)
│   ├── diag_*.py                               # Diagnostics de matching (Phase 3)
│   ├── test_extraction_*.py, schema_extraction.py             # Comparaison de modèles LLM (Phase 4)
│   └── check_classification.py                 # Contrôle qualité post-run
├── dashboard/                                  # Restitution (Phase 6a)
│   ├── generer_rapport.py                      # Assemble le rapport, aucun chiffre en dur
│   ├── theme_millimeter.py                     # Thème Plotly Millimeter Dark
│   ├── template_rapport.html                   # Gabarit, KPI et sections
│   ├── requetes.sql                            # Requêtes documentées hors du Python
│   ├── preparer_polices.py                     # Fabrique les WOFF2, à relancer si l'identité change
│   └── fonts/                                  # Polices sous-ensemblées + licences OFL
├── notebooks/
│   └── 01_exploration_marche.ipynb             # Exploration commentée du corpus courant
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
# Ingestion (Phase 1) : produit data/raw/offres_<horodatage>.json
python3 pull_complet.py

# Enrichissement SIRENE/DINUM (Phase 3) : nécessite dbt run préalable (lit fct_offre)
python3 enrichissement_dinum.py

# Extraction de compétences (Phase 4) : nécessite Ollama + mistral-nemo.
# Reprise incrémentale : seules les offres absentes des dumps précédents sont
# traitées, et un point de reprise est écrit toutes les 25 offres. Mesuré :
# 27,8 s/offre, soit ~3h pour 408 nouvelles offres.
ollama pull mistral-nemo
python3 extraction_skills.py

# Historique de présence (Phase 5) : lit le dump le plus récent et note les
# offres réellement vues cette semaine-là. Idempotent : rejouer un dump déjà
# traité n'ajoute aucune ligne.
python3 presence_offres.py

# Snapshot du corpus (Phase 5) : une ligne par semaine ISO, en upsert :
# une relance en cours de semaine écrase la ligne au lieu de la dupliquer.
python3 snapshot_hebdo.py

# Rapport HTML (Phase 6a) : régénéré à chaque run du pipeline.
python3 dashboard/generer_rapport.py
```

Chaque exécution produit un fichier horodaté distinct : rien n'est écrasé, l'historique des runs est conservé.

## Anatomie des fichiers produits

Les trois scripts (ingestion, enrichissement, extraction) produisent la même structure `{metadata, resultats}`, pour la traçabilité de l'exécution et pas seulement des données :

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

## Exemple de run : ingestion (17/07/2026)

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

- [x] **Phase 1 : Ingestion** : API France Travail, OAuth2, dédoublonnage. 552 offres uniques (dump de référence).
- [x] **Phase 2 : Socle dbt** : staging, intermediate, marts, tests. `fct_offre` exposée et testée.
- [x] **Phase 3 : Enrichissement** : matching SIRENE/DINUM (80,3 %), `dim_entreprise`.
- [x] **Phase 4 : Extraction skills** : schéma d'extraction structuré, comparaison de modèles, `fct_offre_technologie` / `fct_offre_domaine`. Reclassification `INTERMEDIAIRE_reclasse` (33 offres, texte libre) en aval.
- [x] **Phase 5 : Snapshot & historique** : GitHub Actions opérationnel (cron hebdo + déclenchement manuel), dégradation CI sans LLM vérifiée dans les deux sens. `fct_marche_hebdo` et `fct_marche_flux` construits et testés. Quatre semaines de corpus, deux points de flux.
- [ ] **Phase 6 : Restitution** (en cours)
  - [x] Rapport HTML statique Millimeter Dark : polices embarquées, quatre KPI, six sections, dégradation propre sans extraction LLM
  - [x] README : architecture, décisions, limites assumées
  - [x] Notebook d'exploration réécrit sur le corpus courant, 51 blocs de commentaire pour 30 cellules de code
  - [x] CI sur chaque poussée : validation du graphe dbt complet, tests compris, sans aucune clé d'API
  - [ ] ~~Slim CI~~ : écarté par la mesure : le build complet prend 1,79 s, et `--defer` suppose un environnement persistant que l'architecture n'a pas. Voir les décisions
  - [ ] Dashboard interactif, stack à arbitrer sur une mesure coût/bénéfice
  - [ ] ~~Elementary~~ : écarté tant qu'il n'y a pas de warehouse persistant, voir les limites

---

## Limites connues et assumées

Un projet honnête documente ce qu'il ne sait pas résoudre plutôt que de le cacher.

- **Plafond API France Travail** : 1 150 résultats par recherche (pagination `Range` 0–1149). Au-delà, il faudrait affiner (ex. par date). Hors scope pour l'instant.
- **Index temps réel** : la pagination s'effectue sur un index vivant, d'où des doublons possibles au sein d'une même catégorie, mesurés, non corrigés à l'ingestion (dédoublonnage différé à `stg_ft_offres`, par design).
- **EY non matché** (28 offres, 13 %) : sigle commercial absent du répertoire SIRENE, aucun critère fiable pour départager les 5+ entités juridiques du groupe. Non matché volontairement plutôt que par une règle arbitraire.
- **Consolidation groupe sur homonymes** (27 cas) : les filiales portant un nom identique à leur maison mère sont rattachées à la plus grande structure (`nombre_etablissements` maximal), un choix justifié par l'objectif analytique (caractériser le type de structure qui recrute), pas une approximation cachée. Statut distinct en base pour filtrer ce comportement si besoin.
- **Extraction LLM sur le champ `domaines`** : le modèle retenu (Mistral-Nemo) sous-extrait ce champ sur les annonces de conseil en stratégie, au bénéfice d'une bien meilleure fiabilité sur le champ `technologies`, jugé prioritaire pour l'objectif du projet.
- **Bornes de plausibilité salariale, annuel seulement** : la règle existe pour les salaires annuels (260 offres plausibles sur 275, drapeau `salaire_annuel_plausible`). Les populations horaire et mensuelle, 4 et 34 offres, restent sans bornes : trop peu nombreuses pour fonder un seuil défendable. C'est aussi ce qui a fait écarter l'idée de reclasser les valeurs aberrantes vers ces périodes plutôt que de les marquer.
- **Salaire affiché sur moins d'un tiers des offres** : 32,6 % mentionnent un salaire, 27,1 % un salaire annuel exploitable. Toute analyse salariale porte donc sur un quart du corpus, et rien ne dit que ce quart soit représentatif : afficher un salaire est en soi un comportement d'employeur, mesuré ici comme tel.
- **Salaires en paliers** : 66,1 % des montants annuels sont des multiples de 5 000 €. Aucune précision revendiquée sous ce palier.
- **Quasi-doublons résiduels** : la détection repose sur l'identité stricte du texte normalisé. Deux annonces d'une même campagne dont le texte diffère de quelques mots restent comptées séparément : mesuré sur une campagne de onze annonces, neuf sont regroupées et deux échappent. Aller plus loin demande un seuil de similarité, que rien ne permet de calibrer sur ce volume.
- **Le tag ROME de la source n'est pas fiable** : 33 libellés portent une ou deux offres chacun, dont « Assistant comptable » ou « Documentaliste », soit 39 offres et 4,1 % du corpus. Elles sont entrées par les mots-clés ou par un tag erroné. Non filtrées, parce qu'une règle de nettoyage construite sur si peu d'exemples ne serait pas défendable ; visibles et mesurables plutôt que masquées.
- **Corpus accumulé et marché réel sont deux choses** : `fct_offre` et `fct_marche_hebdo` comptent toutes les offres jamais collectées, y compris celles qui ont disparu de France Travail. Seule `fct_marche_flux` mesure le marché vivant. Les deux tables coexistent avec leur portée documentée en tête de modèle plutôt qu'une seule ambiguë.
- **Elementary reste hors de portée** : l'outil stocke ses résultats dans le warehouse, or `warehouse.duckdb` est éphémère sur un runner jetable : il repartirait de zéro chaque lundi. La Phase 6 le prévoyait ; il restera écarté tant que le projet n'a pas de warehouse persistant, ce qui sortirait de la contrainte 0 € d'infrastructure.
- **Snapshot automatisé sans extraction LLM** : le runner GitHub Actions ne peut pas exécuter Ollama (~28 s par offre). Le snapshot hebdomadaire produit par le cron ne comporte donc jamais `top_technologie` ni la reclassification `INTERMEDIAIRE_reclasse` (valeurs marquées explicitement "non disponible (CI)" plutôt que silencieusement fausses ou absentes). Ces deux métriques restent disponibles uniquement après un run manuel en local, extraction Ollama à jour.

## Suite prévue

- **Phase 6b** : dashboard interactif, à arbitrer sur une mesure coût/bénéfice plutôt que sur une préférence de stack.
- **Warehouse persistant** : seule question encore ouverte côté infrastructure, et elle conditionne Elementary. Un service gratuit type MotherDuck la trancherait, au prix d'une dépendance externe que le projet n'a pas aujourd'hui.
- **Longue traîne des domaines** : le mapping couvre 19,7 % des mentions, taux identique à celui mesuré sur 552 offres alors que le corpus a presque doublé. La traîne grossit au même rythme que les douze clusters de tête, donc rien à retravailler pour l'instant. À revérifier si le taux décroche.
- **Phase 6** : dashboard, tests de qualité continus (Elementary, a besoin de cet historique pour détecter des dérives), README enrichi des enseignements finaux.