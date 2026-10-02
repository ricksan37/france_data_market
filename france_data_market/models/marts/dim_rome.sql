{{ config(materialized='table') }}

-- dim_rome: ROME occupations of the latest job offers dump.
-- Grain: one row per ROME code. Key: rome_code.
-- Fed from the offers themselves, not from the exported ROME reference
-- table: the export and the live API can diverge in version, and the label
-- kept is the one the API serves. An offer carries a single ROME code and
-- the pull queries the eight codes of the collection scope (CATEGORIES in
-- full_pull.py), so the table holds the scope codes that have at least one
-- offer; a scope code with no offer in the dump has no row.

select distinct
    rome_code,
    rome_label

from {{ ref('stg_raw__ft_job_offers') }}
