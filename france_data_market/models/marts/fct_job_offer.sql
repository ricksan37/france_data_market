-- fct_job_offer: fine-grained fact table.
-- Grain: one row per job offer. Key: job_offer_id.
-- Assembles stg_raw__ft_job_offers (raw facts) with the int_ layer's
-- enrichments: salary parsing (int_job_offer_salary) and employer
-- classification (int_employer_classification). Left join from
-- stg_raw__ft_job_offers: the fact table must never lose rows because an
-- enrichment is missing or late.
-- rome_code and postal_code stay as raw foreign keys toward dim_rome /
-- dim_commune (no join here, see the relationships tests, point 6).
--
-- employer_name: defaults to France Travail's structured value (100%
-- reliable). Scoped only to employer_category = 'INTERMEDIARY_RECLASSIFIED'
-- (21 offers), it's replaced by employer_name_text, LLM-extracted from the
-- offer's body. The scope is deliberately restricted to that one status:
-- it's precisely the column that traces that a value comes from text rather
-- than the structured field, so no silent mixing -- an unstructured name
-- only appears where the status already signals it.
select
    f.job_offer_id,
    f.job_title,
    f.job_offer_creation_date,
    f.job_offer_last_updated_date,
    f.rome_code,
    f.rome_label,
    f.contract_type,
    f.required_experience,
    f.postal_code,
    f.commune_code,

    -- Unified geographic key: postal code when it exists, INSEE code
    -- otherwise. See dim_commune for why (Paris, Lyon and Marseille have no
    -- single postal code and arrive without one).
    coalesce(f.postal_code, f.commune_code) as commune_key,

    -- Zone rather than a restriction of scope. The question "what if we
    -- limited to mainland France?" was measured on 2026-09-04: overseas
    -- territories weigh 17 offers out of 960, and excluding them doesn't
    -- move any metric (masked employer 33.6 -> 33.0%, identical salary
    -- median). Restricting would cost 5 real, distinct employers for no
    -- gain. The zone is therefore exposed as a dimension: filtering becomes
    -- a one-line clause, available on demand, without touching the spec or
    -- discarding data. Chained comparisons and not IN(): known DuckDB
    -- optimizer bug.
    case
        when coalesce(f.postal_code, f.commune_code) is null then 'unknown'
        when substr(coalesce(f.postal_code, f.commune_code), 1, 2) = '97'
          or substr(coalesce(f.postal_code, f.commune_code), 1, 2) = '98'
            then 'overseas'
        else 'mainland'
    end as geographic_zone,
    case
        when c.employer_category = 'INTERMEDIARY_RECLASSIFIED' then k.employer_name_text
        else f.employer_name_raw
    end as employer_name,
    f.naf_code_on_offer as naf_code,
    f.salary_label,
    f.position_count,
    f.job_description,
    s.salary_min,
    s.salary_max,
    s.salary_period,
    s.salary_mentioned,
    s.annual_salary_plausible,

    -- Identical listing clusters. See int_job_listing_clusters: the same
    -- position published in several cities gets one identifier per city and
    -- so counts that many times in every aggregate. Filtering on
    -- is_canonical_listing counts listings, not filtering counts offers.
    -- Both questions are legitimate.
    g.listing_signature,
    g.cluster_size,
    g.is_canonical_listing,
    c.employer_category,
    d.siren
from {{ ref('stg_raw__ft_job_offers') }} as f
left join {{ ref('int_job_offer_salary') }} as s
    on f.job_offer_id = s.job_offer_id
left join {{ ref('int_employer_classification') }} as c
    on f.job_offer_id = c.job_offer_id
left join {{ ref('stg_dinum__companies') }} as d
    on f.job_offer_id = d.job_offer_id
left join {{ ref('stg_extraction__skills') }} as k
    on f.job_offer_id = k.job_offer_id
left join {{ ref('int_job_listing_clusters') }} as g
    on f.job_offer_id = g.job_offer_id
