with ft_job_offers as (

    select * from {{ ref('stg_raw__ft_job_offers') }}

),

extraction_skills as (

    select * from {{ ref('stg_extraction__skills') }}

),

classified as (

    select
        s.job_offer_id,
        -- Note: no IN(...) here. This DuckDB engine (1.5.4) crashes with an
        -- INTERNAL Error ("index 4 within vector of size 4") as soon as a
        -- view containing a multi-value IN() is queried (GROUP BY, JOIN,
        -- WHERE...) -- same optimizer bug as point 0 (accepted_values,
        -- NOT IN). General workaround: chained = / OR.
        case
            when s.naf_code_on_offer = '62.02A'
                or s.naf_code_on_offer = '78.20Z'
                or s.naf_code_on_offer = '78.10Z'
                or s.naf_code_on_offer = '70.22Z'
                or s.employer_name_raw = 'Michael Page'
                or s.employer_name_raw = 'Fed Group'
                or s.employer_name_raw = 'NEXTGEN RH'
                or s.employer_name_raw = 'STEP UP'
                or s.employer_name_raw = 'Mercato de l''emploi'
                or s.employer_name_raw = 'Externatic'
                or s.employer_name_raw = 'Capgemini'
                or s.employer_name_raw = 'Accenture'
                or s.employer_name_raw = 'CGI'
                or s.employer_name_raw = 'Sopra Steria'
                or s.employer_name_raw = 'Astek'
                or s.employer_name_raw = 'Akkodis'
                or s.employer_name_raw = 'Amaris'
                or s.employer_name_raw = 'Alteca'
                or s.employer_name_raw = 'Randstad professional'
                or s.employer_name_raw = 'ADECCO'
                or s.employer_name_raw = 'CRIT INTERIM'
                then 'INTERMEDIARY'
            when s.employer_name_raw is not null then 'DIRECT_EMPLOYER'
            -- Reclassification: offers with no usable NAF/name (hence
            -- ANONYMOUS by the structural criterion), but where the offer's
            -- text explicitly reveals that the advertiser is acting for a
            -- masked end client (end_client_masked, LLM-extracted from the
            -- description). A distinct status rather than merging into
            -- 'INTERMEDIARY': same principle as match_consolidated_group_* --
            -- to trace and filter downstream without silently correcting a
            -- category built on a different criterion (free text vs
            -- structured NAF/name).
            when k.end_client_masked = true then 'INTERMEDIARY_RECLASSIFIED'
            else 'ANONYMOUS'
        end as employer_category
    from ft_job_offers as s
    left join extraction_skills as k
        on s.job_offer_id = k.job_offer_id

)

select * from classified
