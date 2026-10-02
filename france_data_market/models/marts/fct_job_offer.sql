{{ config(materialized='table') }}

-- fct_job_offer: fine-grained fact table, the table to query for analysis.
-- Grain: one row per job offer of the latest job offers dump. Key:
-- job_offer_id.
-- Assembles stg_raw__ft_job_offers (raw facts) with every enrichment: salary
-- parsing (int_job_offer_salary_parsed), employer classification
-- (int_employers_classified), listing clusters (int_job_offers_clustered),
-- the DINUM SIREN (stg_dinum__companies) and the LLM-extracted employer name
-- (stg_extraction__skills). Left joins from stg_raw__ft_job_offers: the fact
-- table must never lose rows because an enrichment is missing or late.
-- rome_code and commune_key are foreign keys toward dim_rome / dim_commune
-- (no join here; the relationships tests enforce them).
--
-- employer_name: defaults to France Travail's structured value (100%
-- reliable). Scoped only to employer_category = 'INTERMEDIARY_RECLASSIFIED',
-- it's replaced by employer_name_text, LLM-extracted from the
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

    -- Geographic key toward dim_commune: the INSEE code. See dim_commune for
    -- why it is not the postal code.
    f.commune_code as commune_key,

    -- A zone rather than a restriction of scope: overseas offers stay in the
    -- table and leaving them out is a one-line filter. Excluding them moves
    -- no metric (2026-09-26 dump: 5 overseas offers; non-direct employer
    -- share 68.7% vs 68.4%, same median salary), so restricting the scope
    -- would only discard real employers. Overseas postal and INSEE codes
    -- start with 97 (DOM) or 98 (COM).
    case
        when coalesce(f.postal_code, f.commune_code) is null then 'unknown'
        when substr(coalesce(f.postal_code, f.commune_code), 1, 2) in ('97', '98')
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

    -- Identical listing clusters (see int_job_offers_clustered): a listing
    -- published several times, in several communes or again in the same
    -- one, gets one identifier per publication and counts that many times in
    -- every aggregate. Filtering on is_canonical_listing counts listings;
    -- not filtering counts offers. Both questions are legitimate.
    g.listing_signature,
    g.cluster_size,
    g.is_canonical_listing,
    c.employer_category,
    d.siren
from {{ ref('stg_raw__ft_job_offers') }} as f
left join {{ ref('int_job_offer_salary_parsed') }} as s
    on f.job_offer_id = s.job_offer_id
left join {{ ref('int_employers_classified') }} as c
    on f.job_offer_id = c.job_offer_id
-- Restricted to DIRECT_EMPLOYER: the DINUM dump keeps the category an offer
-- had when it was enriched, so an offer reclassified since (e.g. ALTECA,
-- matched to its own SIREN while still DIRECT_EMPLOYER) would otherwise keep
-- an intermediary's SIREN as its employer.
left join {{ ref('stg_dinum__companies') }} as d
    on f.job_offer_id = d.job_offer_id
    and c.employer_category = 'DIRECT_EMPLOYER'
left join {{ ref('stg_extraction__skills') }} as k
    on f.job_offer_id = k.job_offer_id
left join {{ ref('int_job_offers_clustered') }} as g
    on f.job_offer_id = g.job_offer_id
