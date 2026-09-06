-- Staging model for the weekly market snapshot.
-- Grain: 1 row = 1 ISO week, identified by that week's Monday.
-- No business logic here: explicit typing, nothing else.
--
-- Why cast rather than let read_csv_auto infer: reclassified_intermediary_offer_count
-- is empty on every week produced in CI (the reclassification depends on LLM
-- extraction fields, absent from the runner). The inferred type of an
-- entirely empty column depends on which rows are present at run time -- it
-- would therefore drift week to week. An explicit cast freezes the model's
-- contract independently of the file's content.

with source as (

    select * from {{ source('history', 'weekly_market') }}

),

renamed as (

    select
        week_start_date::date as week_start_date,
        total_offer_count::integer as total_offer_count,
        anonymous_offer_count::integer as anonymous_offer_count,
        intermediary_offer_count::integer as intermediary_offer_count,
        reclassified_intermediary_offer_count::integer as reclassified_intermediary_offer_count,
        direct_employer_offer_count::integer as direct_employer_offer_count,
        median_annual_salary::double as median_annual_salary,
        top_technology::varchar as top_technology,
        llm_extraction_available::boolean as llm_extraction_available

    from source

)

select * from renamed
