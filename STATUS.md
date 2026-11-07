# France Data Market: status as of 2026-11-07

Working rules: [CLAUDE.md](CLAUDE.md).

## State
- Weekly pipeline: `weekly_pull.yml` runs every Monday at 06:00 UTC (ingestion, presence history, dbt build, snapshot, DINUM enrichment, report, GitHub Pages).
- 2026-10-05, first run on the eight-ROME-code scope and on dbt 2.0.6: ingestion, build, snapshot and report passed. The DINUM step was rejected by `assert_match_status_valid`: 14 of 263 offers got HTTP 429 from the DINUM API on all five attempts. The tables of the first build stayed in place and the run stayed green (`continue-on-error`).
- Fix `8c0b38a`: retry waits of 5, 15, 45 and 90 s (was 2, 4, 8 and 16 s), `Retry-After` honoured when sent.
- A manual rerun the same evening (816 offers, 262 DINUM offers) had 0 HTTP error, 0 retry, a 90.5 % match rate, and ran in 7 min 41 s (39 min in the morning). The fix itself was not exercised.
- Commit `ea31b10`: `upload-artifact` v7, `upload-pages-artifact` v5, `deploy-pages` v5 (Node 24), runners pinned to `ubuntu-24.04` (`ubuntu-latest` moves to Ubuntu 26 on 2026-10-19). The rerun showed no warning.
- CI scans the whole git history for secrets with gitleaks 8.30.1 on every push (public repository).
- CI dataset: the versioned job offers dump is now the 2026-10-05 pull (eight-ROME-code scope, 814 offers, 3.6 MB). The 2026-07-17 dump left the repository on 2026-10-05; it stays in the git history.
- README findings 2 to 4 re-measured on the 2026-10-05 pull (eight-ROME-code scope, 814 offers, 792 distinct listings); the GitHub profile README carries the same figures.
- 2026-10-12 scheduled run (started 14:20 UTC, not 06:00): 751 offers, 32 retries (all HTTP 429, none past the second attempt), 0 `technical_error`, 90.0 % match rate (217/241), DINUM dump adopted, enrichment in 13 min 42 s. The fix held, though not in the 06:00 slot of 2026-10-05.
- 2026-10-13: the report no longer states the withdrawn July exit figure (552 / 463) and gives the eight-ROME-code scope; retried DINUM calls now log the `Retry-After` header.
- 2026-10-13: `notebooks/01_market_exploration.ipynb` removed; recoverable from the Git history. Its HTML export and the rest of `notebooks/` stay.
- 2026-10-13: the report's weekly series restart at the latest series break (`seeds/series_breaks.csv`), commit `f429e52`; checked locally, live with the next scheduled run.
- 2026-11-07: project closed; the weekly workflow keeps running.
- Weekly runs of 2026-10-19, 10-26 and 11-02 were green (807 offers, 794 listings on 11-02). The 10-26 run spent 5 h 19 in the DINUM step, cause unknown: the step is now capped at 90 minutes.
- `Retry-After` read on the 10-26 run: 4 s on 48 of 49 retries, under the 5 s base wait.
- Published page checked on 2026-11-07: flow from 12/10, masked employers from 05/10, new subtitle and section 01. `report_preview.png` regenerated.
- `is_data_job` added to `fct_job_offer`: 571 of 792 listings; precision 100%, recall 94.9% on 100 labelled listings.
- `mapping_domaines` extended to 17 clusters, 30.7% of mentions.

## Data history
- Dumps collected before 2026-09-29 used a different scope (ROME codes plus keywords) and are not comparable with later ones.
- `weekly_market.csv` points before 2026-10-05 also counted the versioned 2026-07-17 dump and are not comparable with later ones.

## Known gaps
- `is_data_job` reads the title only: a title with no data term stays false.
- The 5 matches flagged by the 2026-10-05 quality audit stay a known limit (0.4% of matches, under the 2% bar).
- 20 commits (2026-09-04 to 2026-09-30) carry a Co-Authored-By line. The history is left as is: the repository is public, and rewriting it would need a force-push and change every later hash.

## Open points
- None. The six-week exit rate can be measured from 2026-11-16.

## How to resume
- `source .venv/bin/activate`. Python scripts run from the repo root, dbt commands from `france_data_market/`.
- `git pull` before any push: the weekly workflow commits to `main`.
- Last weekly run: `gh run list --workflow=weekly_pull.yml`, then `gh run view <id> --log`.
- Long local extraction: `caffeinate -i python3 extract_skills.py` keeps the Mac awake. Never start two instances: both read the same already-extracted ids at launch and extract the same offers twice, and two launches in the same minute write the same dump file.
