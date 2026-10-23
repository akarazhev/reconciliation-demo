{% macro load_scoped_rows(rows, cfg, bounds) %}
    {#- Source rows in the period, and target rows of the same keys or, for keys only in the target, in the period
        themselves (spec §5): the rows both the totals and the null profile count. -#}
    source_rows as (
        {{ load_side_rows(rows, cfg, 'source') }}
    ),
    target_rows as (
        {{ load_side_rows(rows, cfg, 'target') }}
    ),
    source_in as (
        select * from source_rows where {{ load_in_scope('_period', bounds) }}
    ),
    target_in as (
        select t.* from target_rows as t
        where exists (select 1 from source_in as s where s._key = t._key)
           or (not exists (select 1 from source_rows as s where s._key = t._key)
               and {{ load_in_scope('t._period', bounds) }})
    )
{%- endmacro %}

{% macro compare_totals(rows, cfg, bounds) %}
    {#- Rows and the sum of the measure on each side, by period. -#}
    with
    {{ load_scoped_rows(rows, cfg, bounds) }},
    source_totals as (
        select _period as period, count(*) as rows, sum(_amount) as amount from source_in group by _period
    ),
    target_totals as (
        select _period as period, count(*) as rows, sum(_amount) as amount from target_in group by _period
    )
    select
        '{{ var("dataset") }}' as dataset, '{{ cfg["entity"] }}' as entity,
        coalesce(s.period, t.period) as period,
        coalesce(s.rows, 0) as source_rows, coalesce(s.amount, 0)::decimal(18, 4) as source_amount,
        coalesce(t.rows, 0) as target_rows, coalesce(t.amount, 0)::decimal(18, 4) as target_amount
    from source_totals as s
    full outer join target_totals as t on s.period is not distinct from t.period
{% endmacro %}

{% macro compare_nulls(rows, cfg, bounds) %}
    {#- The null profile: NULLs per column on each side, over the same rows as the totals. -#}
    with
    {{ load_scoped_rows(rows, cfg, bounds) }}
    {%- for column in load_list(cfg['columns']) %}
    select
        '{{ var("dataset") }}' as dataset, '{{ cfg["entity"] }}' as entity, '{{ column }}' as column_name,
        (select count(*) from source_in where {{ column }} is null) as source_nulls,
        (select count(*) from target_in where {{ column }} is null) as target_nulls
    {%- if not loop.last %}
    union all
    {%- endif %}
    {%- endfor %}
{% endmacro %}
