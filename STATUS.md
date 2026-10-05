# France Data Market: status as of 2026-10-05

Working rules: [CLAUDE.md](CLAUDE.md).

## State
- Weekly pipeline: `weekly_pull.yml` runs every Monday at 06:00 UTC (ingestion, presence history, dbt build, snapshot, DINUM enrichment, report, GitHub Pages).
- 2026-10-05, first run on the eight-ROME-code scope and on dbt 2.0.6: ingestion, build, snapshot and report passed. The DINUM step was rejected by `assert_match_status_valid`: 14 of 263 offers got HTTP 429 from the DINUM API on all five attempts. The tables of the first build stayed in place and the run stayed green (`continue-on-error`).
- Fix `8c0b38a`: retry waits of 5, 15, 45 and 90 s (was 2, 4, 8 and 16 s), `Retry-After` honoured when sent.
- A manual rerun the same evening (816 offers, 262 DINUM offers) had 0 HTTP error, 0 retry, a 90.5 % match rate, and ran in 7 min 41 s (39 min in the morning). The fix itself was not exercised.
- Commit `ea31b10`: `upload-artifact` v7, `upload-pages-artifact` v5, `deploy-pages` v5 (Node 24), runners pinned to `ubuntu-24.04` (`ubuntu-latest` moves to Ubuntu 26 on 2026-10-19). The rerun showed no warning.

## Data history
- Dumps collected before 2026-09-29 used a different scope (ROME codes plus keywords) and are not comparable with later ones.
- `weekly_market.csv` points before 2026-10-05 also counted the versioned 2026-07-17 dump and are not comparable with later ones.

## Known gaps
- No dbt model yet qualifies an offer as data / not data.
- The README still describes the former scope, and still mentions a DuckDB optimizer bug on multi-value `IN()` that does not reproduce on DuckDB 1.5.4 (tested on real views): `IN()` is fine.

## Open points
- Monday 2026-10-12, 06:00 UTC, first scheduled run since the fix: count the `HTTP error for` lines (expected 0) and the `retry n/4` lines (403 on 2026-10-05), and check whether a 429 carries a `Retry-After` header (the log does not print headers). If `technical_error` persists: requeue the failed offers after a 60 s pause.
- CI dataset: replace the versioned 2026-07-17 job offers dump with one collected on the current scope.

## How to resume
- `source .venv/bin/activate`. Python scripts run from the repo root, dbt commands from `france_data_market/`.
- `git pull` before any push: the weekly workflow commits to `main`.
- Last weekly run: `gh run list --workflow=weekly_pull.yml`, then `gh run view <id> --log`.
