{{ config(materialized='table') }}

-- dim_rome: reference table of ROME occupations present in the scope.
-- Grain: one row per ROME code. Key: rome_code.
-- Fed from the offers themselves (not from the exported ROME reference
-- table): a measurement established that the export and the live API can
-- diverge in version. Since the scope is hybrid (codeROME + motsCles), the
-- codes go beyond the two explicitly targeted (M1405, M1811).

select distinct
    rome_code,
    rome_label

from {{ ref('stg_raw__ft_job_offers') }}
