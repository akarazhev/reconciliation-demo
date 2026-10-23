{% macro compare_rows(rows, cfg, bounds, codes) %}
    {#- Keys on both sides whose values differ, one row per column (spec §5.2). Only is distinct from: two NULLs
        are equal. A key the target holds twice is compared with its first copy; the copy itself is a key difference. -#}
    {%- set kinds = load_column_kinds(load_relation(cfg['entity'], 'source')) -%}
    {%- set first_copy = ((cfg['run_column'] ~ ', ') if cfg['run_column'] else '') ~ '_amount' -%}
    with
    source_rows as (
        {{ load_side_rows(rows, cfg, 'source') }}
    ),
    target_rows as (
        select * from ({{ load_side_rows(rows, cfg, 'target') }})
        qualify row_number() over (partition by _key order by {{ first_copy }}) = 1
    )
    {%- for column in load_list(cfg['columns']) %}
    select
        '{{ var("dataset") }}' as dataset, '{{ cfg["entity"] }}' as entity,
        {{ load_value_cause(rows, cfg, column, kinds[column], codes) }} as cause,
        s._key as key, '{{ column }}' as column_name,
        s.{{ column }}::varchar as source_value, t.{{ column }}::varchar as target_value,
        {%- if kinds[column] == 'number' %}
        (t.{{ column }} - s.{{ column }})::decimal(18, 4) as difference,
        {%- elif kinds[column] == 'time' %}
        (datediff('second', s.{{ column }}, t.{{ column }}) / 3600)::decimal(18, 4) as difference,
        {%- else %}
        null::decimal(18, 4) as difference,
        {%- endif %}
        s._period as period_source, t._period as period_target, s._amount as amount_source, t._amount as amount_target
    from source_rows as s
    join target_rows as t on t._key = s._key
    where {{ load_in_scope('s._period', bounds) }}
      and s.{{ column }} is distinct from t.{{ column }}
    {%- if not loop.last %}
    union all
    {%- endif %}
    {%- endfor %}
{% endmacro %}
