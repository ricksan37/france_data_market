-- Singular test: match_status must be one of the 33 statuses
-- resolve_company() in enrich_dinum.py can emit. Every one of them is
-- listed, not only those observed, so a legitimate status absent from a
-- given dump never fails the build. Derivation: 6 base outcomes (name,
-- name_prefix, word_inclusion, consolidated_group and its _prefix and
-- _inclusion variants) x 4 levels ("", _dept, _national, _national_no_geo),
-- plus 3 _then_naf outcomes on the two levels where NAF tie-breaking is
-- allowed ("", _dept), plus 3 no-match statuses = 33.
--
-- SEVERITY: ERROR. technical_error (an HTTP failure during the run) is
-- deliberately absent: the latest DINUM dump is adopted automatically by
-- stg_dinum__companies, so a dump hit by an API outage must fail the build
-- rather than silently strip offers of their SIREN. A NULL status means a
-- malformed dump and fails too.
-- dbt contract: 0 rows = pass, >= 1 row = fail.
select
    job_offer_id,
    match_status
from {{ ref('stg_dinum__companies') }}
where match_status is null
    or match_status not in (
        'match_name',
        'match_name_dept',
        'match_name_national',
        'match_name_national_no_geo',
        'match_name_then_naf',
        'match_name_then_naf_dept',
        'match_name_prefix',
        'match_name_prefix_dept',
        'match_name_prefix_national',
        'match_name_prefix_national_no_geo',
        'match_name_prefix_then_naf',
        'match_name_prefix_then_naf_dept',
        'match_word_inclusion',
        'match_word_inclusion_dept',
        'match_word_inclusion_national',
        'match_word_inclusion_national_no_geo',
        'match_word_inclusion_then_naf',
        'match_word_inclusion_then_naf_dept',
        'match_consolidated_group',
        'match_consolidated_group_dept',
        'match_consolidated_group_national',
        'match_consolidated_group_national_no_geo',
        'match_consolidated_group_prefix',
        'match_consolidated_group_prefix_dept',
        'match_consolidated_group_prefix_national',
        'match_consolidated_group_prefix_national_no_geo',
        'match_consolidated_group_inclusion',
        'match_consolidated_group_inclusion_dept',
        'match_consolidated_group_inclusion_national',
        'match_consolidated_group_inclusion_national_no_geo',
        'non_matchable_known_acronym',
        'unresolved',
        'unresolved_no_geo'
    )
