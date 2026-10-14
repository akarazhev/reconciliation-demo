{# The only place where shared models learn which platform's staging to read. #}
{% macro platform_ref(name) -%}
{{ ref('stg_' ~ var('platform') ~ '__' ~ name) }}
{%- endmacro %}
