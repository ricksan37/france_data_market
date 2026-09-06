with parsed as (

    select
        job_offer_id,
        salary_label,
        regexp_extract(salary_label, '(Annuel|Mensuel|Horaire) de (\d+(?:\.\d+)?) Euros(?: à (\d+(?:\.\d+)?) Euros)?', 1) as period_text,
        regexp_extract(salary_label, '(Annuel|Mensuel|Horaire) de (\d+(?:\.\d+)?) Euros(?: à (\d+(?:\.\d+)?) Euros)?', 2) as amount_1_text,
        regexp_extract(salary_label, '(Annuel|Mensuel|Horaire) de (\d+(?:\.\d+)?) Euros(?: à (\d+(?:\.\d+)?) Euros)?', 3) as amount_2_text
    from {{ ref('stg_raw__ft_job_offers') }}

),

converted as (

    select
        job_offer_id,
        salary_label,
        period_text as raw_salary_period,
        cast(cast(nullif(amount_1_text, '') as double) as integer) as salary_min,
        cast(cast(nullif(amount_2_text, '') as double) as integer) as salary_max_raw
    from parsed

)

select
    job_offer_id,
    -- Reclassification: a "Mensuel" (monthly) amount > 10000€ isn't plausible
    -- as a monthly salary (max observed ~5400€ in the sample) but is as an
    -- annual one (min observed ~30000€). No ambiguous case between the two
    -- (empty zone 5400-30000€). Measured decision, documented separately.
    --
    -- raw_salary_period keeps the literal French value captured by the regex
    -- (matches France Travail's own text, e.g. "Annuel"): salary_period is
    -- our own translated, reclassified label.
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

    -- Plausibility of the annual amount, bounds [10000, 300000]. NULL when
    -- the question doesn't apply: non-annual period, or no amount. A
    -- three-state boolean rather than two, because "not applicable" isn't
    -- "implausible".
    --
    -- WHY A FLAG AND NOT A PERIOD RECLASSIFICATION. An earlier measurement
    -- reclassified "Mensuel > 10000" as annual, on an empty zone of the
    -- distribution. The symmetric figure exists here: nothing between 1800
    -- and 25000 EUR, i.e. a 23200 EUR gap, and the 15 values under the bound
    -- fall within the observed monthly (506-4000) and hourly (12-25)
    -- distributions. The temptation was therefore real. Cost measured on
    -- 2026-09-03:
    --   - reclassifying the 11 offers at 1800 would take the monthly
    --     population from 34 to 45, 24% of it from A SINGLE advertiser (11
    --     near-identical listings, all ANONYMOUS, all overseas, published
    --     over six days), and its median from 2261 to 1900 EUR
    --   - reclassifying the 4 offers at 15-40 would double the hourly
    --     population, half of it new values, and take its observed maximum
    --     from 25 to 40 EUR
    --   - the gain on the annual side is ZERO: median 45000 with or without them
    -- Two small populations would be damaged for no gain on the large one.
    -- The flag excludes without destroying: the value stays readable, the
    -- aggregation ignores it, and the decision is auditable.
    case
        when raw_salary_period is null then null
        when raw_salary_period != 'Annuel'
             and not (raw_salary_period = 'Mensuel' and salary_min > 10000)
            then null
        when salary_min is null then null
        else salary_min >= 10000 and salary_min <= 300000
    end as annual_salary_plausible
from converted
