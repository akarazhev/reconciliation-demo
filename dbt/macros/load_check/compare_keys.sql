{% macro compare_keys(rows, cfg, bounds) %}
    {#- Rows on one side only, and keys the target holds more than once (spec §5.1, first matching cause). -#}
    with
    source_rows as (
        {{ load_side_rows(rows, cfg, 'source') }}
    ),
    target_rows as (
        {{ load_side_rows(rows, cfg, 'target') }}
    ),
    missing as (
        select
            s._key as key, s._period as period_source, null::date as period_target,
            s._amount as amount_source, null::decimal(18, 4) as amount_target, -1 as difference,
            {%- if cfg['batch_column'] and cfg['order_column'] %}
            case
                when s.{{ cfg['order_column'] }} in (
                    select max({{ cfg['order_column'] }}) from target_rows group by {{ cfg['batch_column'] }})
                    then 'batch_boundary_loss'
                else 'missing_in_target'
            end as cause
            {%- else %}
            'missing_in_target' as cause
            {%- endif %}
        from source_rows as s
        where {{ load_in_scope('s._period', bounds) }}
          and not exists (select 1 from target_rows as t where t._key = s._key)
    ),
    extra as (
        select
            t._key as key, null::date as period_source, t._period as period_target,
            null::decimal(18, 4) as amount_source, t._amount as amount_target, 1 as difference,
            {%- if cfg['parent_entity'] %}
            {%- set parent = load_entity(rows, cfg['parent_entity']) %}
            case
                when t.{{ cfg['parent_column'] }} in (
                    select {{ parent['key'] }} from {{ load_relation(parent['entity'], 'source') }})
                    then 'deleted_left_behind'
                else 'extra_in_target'
            end as cause
            {%- else %}
            'extra_in_target' as cause
            {%- endif %}
        from target_rows as t
        where {{ load_in_scope('t._period', bounds) }}
          and not exists (select 1 from source_rows as s where s._key = t._key)
    ),
    copies as (
        select
            _key as key, count(*) as copies, min(_period) as period_target,
            {%- if cfg['run_column'] %}
            count(distinct {{ cfg['run_column'] }}) as runs,
            sum(_amount) - arg_min(_amount, {{ cfg['run_column'] }}) as amount_target
            {%- else %}
            1 as runs,
            sum(_amount) - min(_amount) as amount_target
            {%- endif %}
        from target_rows
        group by _key
        having count(*) > 1
    ),
    duplicates as (
        select
            c.key, s._period as period_source, c.period_target,
            null::decimal(18, 4) as amount_source, c.amount_target, c.copies - 1 as difference,
            case when c.runs > 1 then 'duplicate_after_rerun' else 'duplicate_in_target' end as cause
        from copies as c
        left join source_rows as s on s._key = c.key
        where {{ load_in_scope('coalesce(s._period, c.period_target)', bounds) }}
    ),
    found as (
        select * from missing
        union all select * from extra
        union all select * from duplicates
    )
    select
        '{{ var("dataset") }}' as dataset, '{{ cfg["entity"] }}' as entity, cause, key,
        null::varchar as column_name, null::varchar as source_value, null::varchar as target_value,
        difference::decimal(18, 4) as difference, period_source, period_target, amount_source, amount_target
    from found
{% endmacro %}
