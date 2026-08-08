{#
    Indique si on tourne dans un environnement sans extraction LLM (CI).
    Lu depuis la variable d'env CI_SANS_EXTRACTION, posée uniquement dans
    .github/workflows/pull_hebdo.yml (Ollama ne tourne pas sur un runner
    GitHub, cf. Session 7). Absente en local -> valeur par défaut 'false'.
#}
{% macro en_ci_sans_extraction() %}
  {{ return(env_var('CI_SANS_EXTRACTION', 'false') == 'true') }}
{% endmacro %}