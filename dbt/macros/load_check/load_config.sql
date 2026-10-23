{% macro load_config_rows() %}
    {#- ref() outside the execute guard gives the calling model a dependency on the table. -#}
    {%- set relation = ref('load_config') -%}
    {%- if not execute -%}
        {{ return([]) }}
    {%- endif -%}
    {%- set result = run_query("select * from " ~ relation ~ " where dataset = '" ~ var('dataset') ~ "' order by entity") -%}
    {%- set rows = [] -%}
    {%- for row in result.rows -%}
        {%- set entry = {} -%}
        {%- for name in result.column_names -%}
            {%- do entry.update({name: row[name]}) -%}
        {%- endfor -%}
        {%- do rows.append(entry) -%}
    {%- endfor -%}
    {{ return(rows) }}
{% endmacro %}

{% macro load_relation(entity, side) %}
    {{ return(ref('stg_' ~ var('dataset') ~ '__' ~ entity ~ '_' ~ side)) }}
{% endmacro %}
