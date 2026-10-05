# France Data Market

A dbt + DuckDB pipeline that collects French data-job postings from the France Travail API every week, enriches them with company data (SIRENE) and a local-LLM skill extraction, and publishes a market report.

**Every non-trivial choice below is backed by a measurement on real data, not a guess.**

**[→ Open the live report](https://ricksan37.github.io/france_data_market/)** (regenerated every Monday by GitHub Actions)

[![Report preview](dashboard/report_preview.png)](https://ricksan37.github.io/france_data_market/)

## What the market says

Measured on the pull of 5 October 2026: 792 distinct listings (814 offers) returned by eight France Travail ROME-code searches (M1405 data scientist, M1811 data engineer, M1419 data analyst, M1868 data architect, M1851 BI analyst, M1824 BI developer, M1872 BI consultant, M1423 chief data officer). Keyword searches were dropped on 2026-09-29 and earlier pulls were truncated (see finding 1), so neither is comparable with these figures. The LLM skill extraction does not run on this pull, as in the weekly report: employers whose text reveals a masked end client are not reclassified and count as masked.

1. ~~**Offers are short-lived.** Of the 552 offers live in mid-July, 463 (84%) had disappeared from France Travail six weeks later.~~ **Invalid, withdrawn on 2026-09-26.** Every pull up to then was truncated by a pagination bug: the API ignored the range the code sent and served the same first page, so the two largest categories (ROME M1811 and "data analyst", 427 and 221 offers on 2026-09-26) were capped at their first 150 offers. An offer that slid out of that first page counted as "disappeared" while still online, so the 84% mixes real exits with truncation and can't be separated after the fact. It will be re-measured on pulls made with the fixed pagination.
2. **Salaries are rarely shown, and almost never when the employer is hidden.** 25.8% of listings disclose a salary: 45.0% for recruitment agencies and IT consultancies (Collective.work excluded, see finding 4), 37.7% for direct employers, 8.3% when the employer's name is masked (about 1 listing in 3).
3. **Where a salary is shown, it sits in a narrow band.** The median annual salary (lower bound) is €45k for direct employers (n=74) and masked employers (n=19), €43k for agencies and consultancies (n=54), €50k for Collective.work missions (n=23). Required experience is what moves it: €45k when experience is required (n=131) vs €40k when beginners are accepted (n=39).
4. **Nearly a fifth of the market is freelance missions from a single platform.** Collective.work, which relays missions for unnamed clients, posted 144 of the 792 listings (18%), all created from 11 September. They rarely fill the salary field (16%) and state a daily rate in the text instead (53 listings mention a TJM), so they're counted as intermediaries and left out of the agency figure above.

Built as a hands-on Analytics Engineering project on a real, messy public dataset. The rest of this page is for technical readers.

---

## A few decisions that show the approach

**Company matching went from 19.2% to 80.3%.** The first attempt (name + postal code) matched one offer in five. Eleven diagnostic rounds later — each triggered by a measurement on real data — the rate reached 80.3% on the 213 eligible offers. Two rules that *worked* were later removed because they produced false positives: the rate gained more in reliability than in volume. Re-run in September on the full corpus with the same rules: 86.8% (614 of 707), and unchanged on the July offers (171 of 213).

**The geographic key wasn't what I assumed, and I only half-fixed it.** The original plan used postal code to join company data. Measured: postal code covers 166 of 213 target offers, INSEE commune code covers 198 — a strict superset. I fixed the company enrichment, but not the geography dimension, which stayed indexed on postal code alone. Paris, Lyon and Marseille are the three French communes with arrondissements: they have no single postal code, so the source returns their overall INSEE code instead, with an empty postal code. Measured: 95 offers affected, 77 of them in Paris — the report was showing 74 Parisian offers instead of 151. A unified key (`coalesce(postal_code, commune_code)`) took coverage from 79% to 89%. The lesson wasn't "fix this one join," it was "this source's geographic key isn't the postal code" — and I'd only applied it locally the first time.

**Three local LLMs, compared blind on a real task.** To extract technical skills from free-text listings, three models ran locally (Ollama) on the same prompt and reference offer: Mistral 7B, Qwen3 8B and Mistral-Nemo 12B. Speed and quality didn't scale simply with size: Qwen3 in "thinking" mode took 258s/offer for a marginal quality gain; turning that off made it 23x faster with no quality loss. Only Nemo reliably told a named product (Azure, Databricks) apart from a technical concept (RAG, CI/CD) — a gap three prompt rewrites couldn't close on the smaller models. The model was picked on that measurement, not its reputation.

**My own fact table was measuring the wrong thing.** `fct_job_offer` once unioned every collected dump and deduplicated: correct for a corpus, wrong for a market reading — an offer seen once stayed in it forever. Measured: of the 552 July offers, 463 had disappeared from France Travail six weeks later, and the corpus still counted them. Two fact tables came out of it: `fct_weekly_market` counts each week's pull (`fct_job_offer` now holds the latest dump only), and `fct_weekly_market_flow` measures actual presence in each pull (`offer_presence.csv`) and is the only table that can say what appears and disappears. The test that keeps it honest ties three independently computed measurements together: a week's active offers must equal the previous week's, minus exits, plus new ones (`552 - 463 + 408 = 497`). The design holds; the figures don't — they were measured on truncated pulls (see the history break below), so the 463 exits are not a market measurement.

**Invisible on the aggregate, destructive on a slice.** Fifteen offers out of 275 carry an implausible annual salary — eleven at 1,800€, four between 15 and 40€/hour mislabeled as annual. On the overall median they change nothing (45,000€ either way). On a slice, they invert it: offers mentioning Tableau showed a median of 1,800€ instead of 37,000€. All eleven 1,800€ offers were also classified `ANONYMOUS`, creating a fake 5,000€ gap against `DIRECT_EMPLOYER` — once excluded, all categories land on the same 45,000€. A flag (`annual_salary_plausible`), not a silent reclassification, excludes them without destroying the value.

**Counting offers vs. counting listings.** Deduplication catches the API's own index duplicates, not marketing campaigns: the same position posted in several cities gets one identifier per city. Measured: 152 offers out of 960 (15.8%) share their exact text with another. Once campaigns are neutralized, two rankings flip: Python (262) overtakes SQL (235), and Data Analysis overtakes Data Governance. Nothing is deleted — a `cluster_size` / `is_canonical_listing` pair exposes the choice, and every report metric states which one it counts.

---

## Repository layout

The eight Python scripts at the root are the pipeline's standalone stages (ingestion, enrichment, extraction, snapshots). The 23 scripts in `exploration/` are diagnostic scripts, kept for traceability: each one produced a measurement cited on this page (matching rates, deduplication, geographic key, salary plausibility), so every figure can be re-derived.

## Architecture

```
France Travail API ──► full_pull.py ──► data/raw/job_offers_*.json ─┐
                                                                         │
DINUM API ──► enrich_dinum.py ──► data/raw/enrich_dinum_*.json ────────┤
                                                                         │
Local LLM (Ollama) ──► extract_skills.py ──► data/raw/extract_skills_*.json ┤
                                                                         ▼
                                                                  dbt sources
                                                                         │
                                                                    staging
                                                                         │
                                                                  intermediate
                                                                         │
                                                                      marts
```

dbt makes no HTTP or LLM calls. Every enrichment follows the same pattern: standalone Python script → timestamped JSON dump in `data/raw/` → dbt source → `stg_` model.

### dbt layers

- **staging** (`stg_`): renaming, casting, deduplication. No business logic.
- **intermediate** (`int_`): salary parsing and plausibility, employer classification, identical-listing clustering, placement of LLM-extracted skills between technologies and domains.
- **marts**: `fct_job_offer` (grain: one offer), `dim_rome`, `dim_commune`, `dim_company`, `fct_job_offer_technology`, `fct_job_offer_domain`, `fct_weekly_market` (each week's pull) and `fct_weekly_market_flow` (presence history: what appears and disappears).

## Continuous integration

Two workflows. `.github/workflows/ci.yml` runs on every push and pull request: compiles the Python scripts, rebuilds the full dbt graph with its tests, generates the report. A second job scans the full git history for secrets with gitleaks (the repository is public). **No secret required** — the reference dumps and snapshot CSVs are versioned, so the pipeline rebuilds from the repo's own data alone. `.github/workflows/weekly_pull.yml` runs every Monday: ingestion, presence history, build, snapshot, DINUM enrichment, report, commit, then deploys the report to GitHub Pages. The runner only has the versioned July dump plus that week's pull (earlier weekly dumps aren't kept), and `stg_raw__ft_job_offers` keeps the most recent dump, so the live report describes that week's pull. The weekly presence history (`offer_presence.csv`) is committed, so it carries over from week to week (see the history break below).

The versioned reference dump is stripped of the `contact` and `agence` fields (recruiter names, emails, phone numbers): France Travail's reuse licence excludes contact data, and `full_pull.py` now drops them at ingestion.

The weekly run can't execute the LLM extraction (Ollama doesn't run on a GitHub runner), so an env var (`CI_WITHOUT_EXTRACTION`) makes the extraction source degrade to zero rows with the same schema. The affected metrics are marked explicitly unavailable rather than silently zero.

## Setup

```bash
git clone <repo>
cd france_data_market
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file at the root (never committed) with France Travail partner credentials:

```
FT_CLIENT_ID=xxxxxxxx
FT_CLIENT_SECRET=xxxxxxxx
```

No API key is needed to reproduce the dbt layer: `profiles.yml` is versioned, DuckDB needs no credentials, and skill extraction runs on a free local model.

```bash
cd france_data_market
dbt debug
dbt run
dbt test
```

## Usage

```bash
python3 full_pull.py        # France Travail ingestion
python3 enrich_dinum.py        # SIRENE/DINUM company enrichment (needs a prior dbt run)
ollama pull mistral-nemo
python3 extract_skills.py      # skill extraction, incremental resume, ~34s/offer
python3 offer_presence.py      # weekly presence history, idempotent
python3 weekly_snapshot.py      # weekly corpus snapshot, upsert
python3 dashboard/generate_report.py   # static HTML report
```

Each run produces a distinct timestamped file: nothing is overwritten.

## Stack

| Component | Version | Why |
|---|---|---|
| dbt | 2.0.6 | dbt v2, the Rust engine; it embeds its DuckDB driver. |
| DuckDB | 1.5.5 | In-process columnar OLAP, zero-copy Arrow/Pandas. The pipeline runs in seconds on a laptop, no server to provision. |
| Ollama + Mistral-Nemo 12B | | Structured skill extraction, locally. No API key, no cost. |
| GitHub Actions | | Weekly pull automation. Disposable runner: only the aggregated snapshot persists between runs. |
| Python | 3.13 | requests, python-dotenv, duckdb, pydantic, ollama, plotly |
## Known limitations

- **France Travail API cap**: 1,150 results per search. Beyond that, the search would need narrowing (e.g. by date).
- **History break on 2026-09-26 — pulls before it were truncated.** Until then, pagination sent its range in an HTTP `Range` header, which the France Travail API silently ignores: every "page" was the same first 150 offers. The duplicates this produced within a category (449 of the 542 in the July dump) were long read as live-index noise and deduplicated away, which hid the bug. Pagination now uses the `range` query parameter, and `full_pull.py` fails before writing any dump if a category fetches fewer unique offers than the API's `Content-Range` total (tolerance: max(5, 2%)). Consequences: `offer_presence.csv`, `fct_weekly_market_flow` and `weekly_market.csv` are **not comparable before and after 2026-09-26** (every week up to 2026-09-21 is truncated). `fct_job_offer` holds the latest dump only, so the truncated dumps no longer enter it. Two later breaks are flagged in `series_breaks.csv`: 2026-09-28 (first untruncated pull of the series) and 2026-10-05 (first pull on the eight-ROME-code scope, and first total measured on the latest dump only).
- **Company enrichment can lag the pull.** `enrich_dinum.py` runs every Monday after the snapshot, in a step allowed to fail (`continue-on-error`). `stg_dinum__companies` keeps the most recent dump, and `assert_match_status_valid` rejects a dump containing an API failure (`technical_error`), as does a matching rate under 75 %: the report then goes out with the SIRENs of the previous dump, and offers collected since have none until the next successful run.
- **"EY" left unmatched** (5 offers in the 2026-10-05 pull): a commercial acronym absent from the SIRENE registry, with 5+ legal entities and no reliable tiebreaker.
- **Group consolidation on homonyms** (29 cases in the 2026-10-05 pull): subsidiaries sharing a name with their parent are attached to the largest entity — a deliberate choice aligned with the analytical goal, flagged with a distinct status.
- **LLM extraction under-extracts the `domains` field** on consulting listings, in exchange for much higher reliability on `technologies`, the field prioritized for this project.
- **Salary plausibility bounds, annual only**: too few hourly/monthly offers (6 and 27 in the 5 October pull) to set a defensible threshold.
- **Salary shown on under a third of listings** (25.8% in the 5 October pull): any salary analysis covers a non-random subset, since disclosing a salary is itself an employer behavior.
- **Residual near-duplicate listings**: detection relies on strict text identity; listings differing by a few words are counted separately.
- **ROME tag isn't fully reliable**: a small number of offers (~4%) carry an unrelated ROME label, entered via keyword match. Left visible rather than filtered by an under-supported rule.
- **Latest pull vs. presence history are two different things**: `fct_job_offer` and `fct_weekly_market` describe each week's pull; `fct_weekly_market_flow` is the only one that measures what appears and disappears between pulls.

## What's next

The report stays a static HTML page: Streamlit and a React app were ruled out as disproportionate. Next: a qualification model that flags offers as data or not data, and revisiting the domain long tail if its coverage rate ever drops below its current, stable ~20%.
