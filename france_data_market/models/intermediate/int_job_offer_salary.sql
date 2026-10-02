-- Parses France Travail's free-text salary_label into a period and a
-- min/max amount, and flags implausible annual amounts.
-- Grain: one row per job offer. Key: job_offer_id.

{% set salary_pattern %}(Annuel|Mensuel|Horaire) de (\d+(?:\.\d+)?) Euros(?: à (\d+(?:\.\d+)?) Euros)?{% endset %}

with parsed as (

    select
        job_offer_id,
        salary_label,
        regexp_extract(salary_label, '{{ salary_pattern }}', 1) as period_text,
        regexp_extract(salary_label, '{{ salary_pattern }}', 2) as amount_1_text,
        regexp_extract(salary_label, '{{ salary_pattern }}', 3) as amount_2_text
    from {{ ref('stg_raw__ft_job_offers') }}

),

converted as (

    select
        job_offer_id,
        salary_label,
        -- regexp_extract returns '' rather than NULL when the label doesn't
        -- match (e.g. "Annuel de 7.5E+7 Euros"): nullif keeps a single
        -- representation of "no period".
        nullif(period_text, '') as raw_salary_period,
        cast(cast(nullif(amount_1_text, '') as double) as integer) as salary_min,
        cast(cast(nullif(amount_2_text, '') as double) as integer) as salary_max_raw
    from parsed

)

select
    job_offer_id,
    -- Reclassification: a "Mensuel" (monthly) amount above 10000 EUR is an
    -- annual salary entered in the wrong field. The distribution leaves no
    -- ambiguous case: monthly amounts go up to 5000 EUR, reclassified ones
    -- start at 33000 EUR (2026-09-26 dump).
    --
    -- raw_salary_period keeps the literal French value captured by the regex
    -- (France Travail's own text, e.g. "Annuel"); salary_period is our own
    -- translated, reclassified label.
    case
        when raw_salary_period = 'Mensuel' and salary_min > 10000 then 'annual'
        when raw_salary_period = 'Annuel' then 'annual'
        when raw_salary_period = 'Mensuel' then 'monthly'
        when raw_salary_period = 'Horaire' then 'hourly'
        else null
    end as salary_period,
    raw_salary_period,
    salary_min,
    coalesce(salary_max_raw, salary_min) as salary_max,
    salary_label is not null as salary_mentioned,

    -- Plausibility of the annual amount, bounds [10000, 300000]. Three
    -- states: NULL when the question doesn't apply (non-annual period, or no
    -- amount), because "not applicable" isn't "implausible".
    -- A flag rather than a correction: an implausible amount stays readable
    -- for audit and aggregations exclude it. Reclassifying it as monthly or
    -- hourly would guess the recruiter's intent and distort the small
    -- monthly and hourly populations (21 and 5 offers on the 2026-09-26 dump).
    case
        when raw_salary_period is null then null
        when raw_salary_period != 'Annuel'
             and not (raw_salary_period = 'Mensuel' and salary_min > 10000)
            then null
        when salary_min is null then null
        else salary_min >= 10000 and salary_min <= 300000
    end as annual_salary_plausible
from converted