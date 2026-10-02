with ft_job_offers as (

    select * from {{ ref('stg_raw__ft_job_offers') }}

),

extraction_skills as (

    select * from {{ ref('stg_extraction__skills') }}

),

classified as (

    select
        s.job_offer_id,
        case
            when s.naf_code_on_offer in ('62.02A', '78.20Z', '78.10Z', '70.22Z')
                or s.employer_name_raw in (
                    'Michael Page',
                    'Fed Group',
                    'NEXTGEN RH',
                    'STEP UP',
                    'Mercato de l''emploi',
                    'Externatic',
                    'Capgemini',
                    'Accenture',
                    'CGI',
                    'Sopra Steria',
                    'Astek',
                    'Akkodis',
                    'Amaris',
                    'Alteca',
                    'Randstad professional',
                    'ADECCO',
                    'CRIT INTERIM',
                    -- Freelance mission platform, not an employer: "notre client
                    -- recherche...", daily rate (TJM) caps, "- Freelance" titles.
                    -- Measured 2026-09-26: 222 offers (all created from
                    -- 2026-09-11), 206 of them mentioning freelance/mission/TJM/
                    -- portage. Left as DIRECT_EMPLOYER, it made up 24% of that
                    -- category and 222 of the 275 unresolved DINUM matches.
                    'Collective.work'
                )
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
