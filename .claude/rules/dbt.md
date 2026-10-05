---
paths:
  - "france_data_market/**"
---

# dbt conventions

- Use the installed dbt agent skills when relevant: `using-dbt-for-analytics-engineering` (build, modify, debug models), `adding-dbt-unit-test`, `running-dbt-commands`, `fetching-dbt-docs`.
- SQL comments and descriptions: `standards-de-code` skill (`~/Developer/personal_agent/.claude/skills/standards-de-code/references/sql-dbt.md`), which routes to the dbt Labs skills for YAML descriptions. Project choice: comments in models use `--` (kept in the compiled SQL), macro headers use `{# #}`.
- Layers and naming: `stg_<source>__<entity>` (one per source table, renaming and typing only), `int_<entity>_<verb>` (business logic), `dim_<entity>` / `fct_<entity>` (marts). Every model has a `.yml` with a description for the model and each column.
- Marts are `materialized='table'`, declared in a `{{ config(...) }}` block at the top of the file.
- `left join` is the default in fact tables, even when an `inner join` would return the same rows today.
- Deduplication with `qualify row_number() over (...) = 1`.
- `select distinct col_a, col_b` deduplicates the pair, never a single column.
- Accepted values are tested with singular tests (`tests/assert_*.sql`), not `accepted_values`. A known, justified anomaly gets `severity: warn` with the justification in the test file, never a silent patch.
- After changing a seed's schema, run `dbt seed --full-refresh` (a plain `dbt seed` inserts into the old table and keeps the old schema).
- Validate with `dbt build` and check row counts against the expected figure before moving on.
