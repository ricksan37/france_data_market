{{ config(
    severity = 'warn',
    tags = ['known_issue']
) }}

-- Coverage of the domain normalization mapping (seeds/mapping_domaines.csv):
-- share of domain mentions whose raw value is a mapped variant.
-- Measured: 19.6% (1144 of 5828 mentions, 2026-09-26 dump), ~20% when the
-- mapping was built. Warns under 15%: new clusters have appeared, or new
-- volume dilutes the mapped ones, and the mapping needs reworking. Above
-- it, the test passes, so a warning is always a signal to act on.
--
-- SEVERITY: WARN. Low coverage degrades the domain breakdown without making
-- it wrong (unmapped values stay as raw_domain), so it doesn't block.
-- dbt contract: 0 rows = pass, 1 row = warn.
select
    count(*) as total_mentions,
    count(*) filter (where raw_domain in (select variant from {{ ref('mapping_domaines') }}))
        as covered_mentions,
    round(100.0 * count(*) filter (where raw_domain in (select variant from {{ ref('mapping_domaines') }}))
        / nullif(count(*), 0), 1) as coverage_rate_pct
from {{ ref('fct_job_offer_domain') }}
having count(*) > 0
    and count(*) filter (where raw_domain in (select variant from {{ ref('mapping_domaines') }}))
        < 0.15 * count(*)
