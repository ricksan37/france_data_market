{#
    Indicates whether we're running in an environment without LLM extraction (CI).
    Read from the env var CI_WITHOUT_EXTRACTION, set only in
    .github/workflows/pull_hebdo.yml (Ollama doesn't run on a GitHub runner).
    Absent locally -> defaults to 'false'.
#}
{% macro in_ci_without_extraction() %}
  {{ return(env_var('CI_WITHOUT_EXTRACTION', 'false') == 'true') }}
{% endmacro %}
