-- Queries for the HTML report (France Data Market Observatory).
-- This file documents the queries independently of their use in Python
-- (dashboard/generate_report.py), a convention established in the Second
-- Brain Extensions (queries.sql next to index.html).
--
-- Only two queries depend on stg_extraction__skills and degrade to zero rows
-- in CI_WITHOUT_EXTRACTION (SECTION 05 and SECTION 06). All the others,
-- including the four KPIs and the flow section, are populated on a runner.

-- ============================================================
-- SCOPE AND KPIs
-- None of these figures is hardcoded in the report. The previous version
-- announced "552 offers" in its subtitle while the corpus already held 960:
-- the scope was frozen in three places in the code.
-- ============================================================

-- SCOPE: number of offers analyzed, shown in the subtitle and as a KPI
select count(*) as n from fct_job_offer;

-- KPI_TRANSPARENCY: share of offers disclosing a salary
select round(100.0 * count(case when salary_mentioned then 1 end)
             / nullif(count(*), 0), 1) as pct
from fct_job_offer;

-- KPI_ANONYMITY: latest known value of the masked-employer rate.
-- Comes from fct_weekly_market rather than a direct computation on
-- fct_job_offer: the KPI must be the same last point as the series
-- displayed just below it, otherwise the two figures could diverge from one
-- run to the next.
select week_start_date, total_offer_count, anonymous_rate_pct
from fct_weekly_market
order by week_start_date;

-- KPI_EXITS: exit rate, latest week where it's measurable.
-- NULL on the first recorded week, for lack of a comparison point: the
-- report then falls back to "N/A" rather than showing zero.
select week_start_date, weeks_since_previous, active_offer_count,
       new_offer_count, exit_count, exit_rate_pct
from fct_weekly_market_flow
order by week_start_date;

-- ============================================================
-- SECTION 01: MARKET FLOW
-- Measured on fct_weekly_market_flow, i.e. on offers' actual presence in
-- each collection. Measuring it on fct_job_offer would be wrong: the corpus
-- accumulates the dumps and never shrinks (960 offers on 2026-08-31, 463 of
-- which had already disappeared from France Travail).
-- ============================================================
-- The two queries are the KPI ones above, reused as-is.

-- ============================================================
-- SECTION 02: COMPENSATION
-- Filters on annual_salary_plausible, not on a hardcoded job_offer_id.
-- The previous version explicitly excluded offer 4933945, the only known
-- case at the time. As of 2026-09-03 there are 15, via two mechanisms: a
-- monthly salary labeled annual (11 listings at 1800 €, a single
-- advertiser) and an hourly rate labeled annual (4 listings, 15 to 40 €).
-- A named exclusion doesn't scale, a rule does.
--
-- Sample size is carried alongside the median and displayed on every bar.
-- Below 10 offers the category is dropped from the chart and named in a
-- note: INTERMEDIARY_RECLASSIFIED used to show 65,000 € at the top, computed
-- on 3 offers.
-- ============================================================

-- SALARY_BY_CATEGORY
select employer_category,
       count(*) as n,
       median(salary_min) as median_salary
from fct_job_offer
where salary_period = 'annual' and annual_salary_plausible
group by employer_category
order by median_salary desc;

-- SALARY_BY_EXPERIENCE
-- required_experience carries France Travail's raw codes. Measured
-- 2026-08-31: only D and E are present (540 and 420 offers), S is absent.
-- Translation to readable labels lives in the generator, never here nor in
-- the dbt models, which keep the canonical values.
select required_experience,
       count(*) as n,
       median(salary_min) as median_salary
from fct_job_offer
where salary_period = 'annual' and annual_salary_plausible
group by required_experience
order by median_salary;

-- ============================================================
-- SECTION 03: SALARY TRANSPARENCY
-- ============================================================

-- TRANSPARENCY_BY_CATEGORY
select employer_category,
       round(100.0 * count(distinct case when salary_mentioned then job_offer_id end)
             / nullif(count(distinct job_offer_id), 0), 1) as rate_pct
from fct_job_offer
group by employer_category
order by rate_pct desc;

-- ============================================================
-- SECTION 04: GEOGRAPHY
-- ============================================================

-- TOP_COMMUNES
-- Joined on commune_key, not on postal_code. Paris, Lyon and Marseille are
-- the three communes with arrondissements: they have no single postal code
-- and arrive with only their overall commune's INSEE code. Before this fix,
-- the report showed 71 Parisian offers where there are actually 148.
select c.commune_name, count(distinct o.job_offer_id) as offer_count
from fct_job_offer o
join dim_commune c on c.commune_key = o.commune_key
where c.commune_name is not null and c.commune_name != 'UNRESOLVED'
group by c.commune_name
order by offer_count desc
limit 10;

-- ============================================================
-- SECTION 05: TECHNOLOGIES
-- Depends on stg_extraction__skills, hence zero rows in CI. The degradation
-- is detected on the empty result, not on the environment variable: we
-- measure the data's actual state rather than an indirect signal.
-- ============================================================

-- TOP10_TECHNOLOGIES
select technology, count(distinct job_offer_id) as offer_count
from fct_job_offer_technology
group by technology
order by offer_count desc
limit 10;

-- ============================================================
-- SECTION 06: DOMAINS
-- Same dependency as section 05.
-- ============================================================

-- DOMAIN_CLUSTERS
-- Filtered by membership in the canonical forms, not by is not null:
-- normalized_domain is never NULL, fct_job_offer_domain's coalesce falls
-- back to the raw value when the mapping doesn't match.
select normalized_domain, count(distinct job_offer_id) as offer_count
from fct_job_offer_domain
where normalized_domain in (select distinct canonical_domain from mapping_domaines)
group by normalized_domain
order by offer_count desc;

-- DOMAIN_COVERAGE
-- Measured 2026-08-31 on 960 offers: 19.7%, identical to the 19.7% measured
-- previously on 552 offers. The long tail grows at the same pace as the
-- twelve top clusters, so the mapping isn't being diluted.
select round(100.0 * count(case when normalized_domain in
             (select distinct canonical_domain from mapping_domaines)
           then 1 end) / nullif(count(*), 0), 1) as pct
from fct_job_offer_domain;
