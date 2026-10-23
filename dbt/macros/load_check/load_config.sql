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

{% macro load_dataset_row() %}
    {#- The dataset's row of load_datasets: its period bounds. ref() outside the guard, as above. -#}
    {%- set relation = ref('load_datasets') -%}
    {%- if not execute -%}
        {{ return({}) }}
    {%- endif -%}
    {%- set result = run_query("select * from " ~ relation ~ " where dataset = '" ~ var('dataset') ~ "'") -%}
    {%- set row = {} -%}
    {%- for name in result.column_names -%}
        {%- do row.update({name: result.rows[0][name]}) -%}
    {%- endfor -%}
    {{ return(row) }}
{% endmacro %}

{% macro load_list(text) %}
    {{ return((text or '').split(';') | map('trim') | reject('equalto', '') | list) }}
{% endmacro %}

{% macro load_entity(rows, entity) %}
    {%- for row in rows if row['entity'] == entity -%}
        {{ return(row) }}
    {%- endfor -%}
    {{ exceptions.raise_compiler_error('load_config has no entity ' ~ entity ~ ' for ' ~ var('dataset')) }}
{% endmacro %}

{% macro load_column_kinds(relation) %}
    {#- time, number or text for every column of a staging model, from the database itself. -#}
    {%- set kinds = {} -%}
    {%- for column in adapter.get_columns_in_relation(relation) -%}
        {%- set dtype = column.dtype | upper -%}
        {%- if dtype.startswith('TIMESTAMP') or dtype == 'DATE' -%}
            {%- do kinds.update({column.name: 'time'}) -%}
        {%- elif dtype.startswith('DECIMAL') or dtype in ('TINYINT', 'SMALLINT', 'INTEGER', 'BIGINT', 'HUGEINT', 'DOUBLE', 'FLOAT', 'REAL') -%}
            {%- do kinds.update({column.name: 'number'}) -%}
        {%- else -%}
            {%- do kinds.update({column.name: 'text'}) -%}
        {%- endif -%}
    {%- endfor -%}
    {{ return(kinds) }}
{% endmacro %}

{% macro load_in_scope(period, bounds) -%}
    ({{ period }} is null or {{ period }} between date_trunc('month', date '{{ bounds['period_start'] }}')
                                             and date_trunc('month', date '{{ bounds['period_end'] }}'))
{%- endmacro %}

{% macro load_side_rows(rows, cfg, side) %}
    {#- One side of an entity with its business key, period and measure. A line takes the period of its document
        (parent_entity), and the document's modification time when the document has one. -#}
    {%- set measures = load_list(cfg['measures']) -%}
    {%- set parent = load_entity(rows, cfg['parent_entity']) if cfg['parent_entity'] else none -%}
    select
        r.*,
        r.{{ cfg['key'] }}::varchar as _key,
        {%- if cfg['period_column'] %}
        date_trunc('month', r.{{ cfg['period_column'] }})::date as _period,
        {%- elif parent and parent['period_column'] %}
        date_trunc('month', p.{{ parent['period_column'] }})::date as _period,
        {%- else %}
        null::date as _period,
        {%- endif %}
        {%- if parent and parent['modified_column'] %}
        p.{{ parent['modified_column'] }} as _parent_modified,
        {%- endif %}
        {{ ('r.' ~ measures[0]) if measures else 'null' }}::decimal(18, 4) as _amount
    from {{ load_relation(cfg['entity'], side) }} as r
    {%- if parent %}
    left join {{ load_relation(parent['entity'], side) }} as p on p.{{ parent['key'] }} = r.{{ cfg['parent_column'] }}
    {%- endif %}
{% endmacro %}

{% macro load_empty_diff() %}
    select null::varchar as dataset, null::varchar as entity, null::varchar as cause, null::varchar as key,
           null::varchar as column_name, null::varchar as source_value, null::varchar as target_value,
           null::decimal(18, 4) as difference, null::date as period_source, null::date as period_target,
           null::decimal(18, 4) as amount_source, null::decimal(18, 4) as amount_target
    where false
{% endmacro %}
