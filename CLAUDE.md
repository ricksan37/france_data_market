# France Data Market

Analytics engineering pipeline on French data job offers: France Travail API ingestion (Python), transformation in dbt + DuckDB, company enrichment (DINUM / SIRENE API), skill extraction with a local LLM (Ollama, mistral-nemo), static HTML report.

## Environment

- Always activate the venv before any `python3` or `dbt` command: `source .venv/bin/activate`. If `dbt debug` shows an unexpected python path despite a correct `which`, run `hash -r`.
- `python3`, never `python`.
- Python scripts run from the repo root. All dbt commands run from `france_data_market/`.
- Stack: Python 3.13, dbt-core 1.11.7, dbt-duckdb 1.10.1, DuckDB 1.5.4 (pinned), Ollama + mistral-nemo.
- DuckDB is single-writer. On `Could not set lock`: `lsof | grep warehouse.duckdb`, close the other process.
- dbt never drops the relation of a renamed or deleted model: after a rename, delete `data/warehouse.duckdb` and rerun `dbt build` (the warehouse is fully rebuilt from `data/` and the seeds).

## Pipeline map

| Step | Entry point | Output |
|---|---|---|
| Ingestion | `full_pull.py` (uses `auth.py`, `search.py`) | `data/raw/job_offers_*.json` |
| Company enrichment | `enrich_dinum.py` | `data/raw/enrich_dinum_*.json` |
| Skill extraction | `extract_skills.py` (local, never in CI) | `data/raw/extract_skills_*.json` |
| Weekly history | `weekly_snapshot.py`, `offer_presence.py` | `data/snapshots/*.csv` |
| Transformation | dbt project in `france_data_market/` | `data/warehouse.duckdb` |
| Report | `dashboard/generate_report.py` | `dashboard/report.html` |

CI: `.github/workflows/ci.yml` runs on every push (compile scripts, `dbt build` on versioned data with `CI_WITHOUT_EXTRACTION=true`, report generation). `weekly_pull.yml` runs the pull weekly. CI never calls the France Travail API outside the weekly job.

## Collection scope

- Scope = 8 ROME codes, listed in `CATEGORIES` in `full_pull.py`: M1405, M1811, M1419, M1868, M1851, M1824, M1872, M1423. An offer has a single ROME code, so categories never overlap.
- ROME codes are declared by recruiters and are never 100 % clean (BI codes also catch business developers). Collection aims at recall; precision belongs to a dbt qualification model (not built yet).
- Out of scope after measurement: M1889 (AI / ML engineer), M1894 (DBA), M1414 (statistician).
- Dumps collected before 2026-09-29 used a different scope (ROME codes plus keywords) and are not comparable with later ones.
- `weekly_market.csv` points before 2026-10-05 also counted the versioned 2026-07-17 dump and are not comparable with later ones.

## France Travail API facts (measured)

- OAuth2 client_credentials; both scopes `api_offresdemploiv2 o2dsoffre` are required, including for search. Token lifetime: 1499 s, never renewed during a pull.
- Pagination only through the `range` query parameter (max 150 per call, ceiling 1150 results). A `Range` header is silently ignored.
- No match: `204` with an empty body and `Content-Range: */0`.
- 401 / 403 bodies are empty; the explanation is in the `WWW-Authenticate` header.
- `full_pull.py` fails before writing a dump if a category is incomplete versus its `Content-Range` total. `--dry-run` runs the pull and the check without writing.
- `contact` and `agence` fields are dropped at ingestion (personal data, excluded by the reuse licence). Otherwise raw files are never modified.

## Settled decisions (reopen only with a new measurement)

- Geographic key = commune INSEE code, not postal code.
- `dim_company.age_years` is a raw column; no `is_startup` flag (age / NAF / headcount do not discriminate).
- Skill extraction model: mistral-nemo 12B. The extraction prompt and its JSON field names stay in French: per-field instructions are anchored to those names.
- The `domains` field is under-extracted on consulting offers: accepted, documented limit.
- The `dinum` dbt source reads every DINUM dump and `stg_dinum__companies` keeps the most recent one (each run supersedes the earlier ones). A run with any `technical_error` fails `dbt build` (`assert_match_status_valid`), and so does a matching rate under 75 % (`assert_dinum_matching_rate_floor`).
- `stg_raw__ft_job_offers` keeps only the most recent job offers dump: `fct_job_offer` describes the market as of the latest pull. Offer history lives in `offer_presence.csv`, built from the raw dumps directly.
- Our own vocabulary (`employer_category`, `salary_period`, `geographic_zone`, `match_status`) is in English; values copied from source text stay in their source language.

## Conventions

- Code comments, docstrings and commit messages are in English.
- Comments document the why, never the what. They describe the code as it is now: no history, no "until X we did Y". Measured facts that justify the code are welcome ("the API answers 204 with an empty body"). History goes in commit messages and the README.
- Verify rather than assume: every step has an expected figure; if it does not land, stop and find out why.
- Before relying on a regex, pattern or mapping, check it on real cases for obvious false positives.
- One shell command at a time; never chain several on one line.
- Git: never run `git commit` or `git push`. Prepare the commit message and the commands; the user runs them. A one-line message without quotes can go through `git commit -m`; a multi-line message goes through `git commit` (editor) or `git commit -F <file>`, because pasting multi-line quoted text breaks zsh quote parsing.
- The weekly workflow commits to `main`: the local copy is often behind. `git pull` (configured to rebase and autostash) before `git push`.

Language-specific rules live in `.claude/rules/` (Python, dbt).

## Known gaps

- No dbt model yet qualifies an offer as data / not data.
- The README still describes the former scope.
- Five singular tests (`assert_contract_type_valid`, `assert_contract_type_valid_fct_job_offer`, `assert_employer_category_valid`, `assert_geographic_zone_valid`, `assert_week_is_a_monday`) still avoid multi-value `IN()` because of a DuckDB optimizer bug that does not reproduce on DuckDB 1.5.4 (tested on real views). `IN()` is fine; the README and `requirements.txt` (whose comments are still in French) still mention the bug.