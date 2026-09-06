{{ config(
    severity = 'warn',
    tags = ['known_issue']
) }}

-- Measures the coverage of the domain normalization mapping
-- (seeds/mapping_domaines.csv), to detect drift rather than discover it
-- silently when new data arrives (Phase 5).
--
-- The current mapping covers ~20% of mentions (the 12 top clusters,
-- measured 2026-08-02 on the 552 real offers). This test never fails
-- (WARN only): its role is to inform, not to block. If the coverage rate
-- drops well below this level with new data, that's the signal to rework
-- the mapping: new clusters appeared, or volume diluting the 12 existing
-- ones.
--
-- Implemented as a test that ALWAYS fails with the figure in the message:
-- dbt has no native mechanism to "display a metric without failing", so
-- WARN is repurposed as a periodic information channel.
select
    count(*) as total_mentions,
    count(case when raw_domain != normalized_domain
               or raw_domain in (select variant from {{ ref('mapping_domaines') }})
          then 1 end) as covered_mentions,
    round(100.0 * count(case when raw_domain != normalized_domain
               or raw_domain in (select variant from {{ ref('mapping_domaines') }})
          then 1 end) / count(*), 1) as coverage_rate_pct
from {{ ref('fct_job_offer_domain') }}
having coverage_rate_pct is not null  -- always true: forces the WARN on every run
