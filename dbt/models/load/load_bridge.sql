{{ config(enabled = var('suite', 'recon') == 'load', tags = ['load_check']) }}
{% for r in var('load_relations', []) %}-- depends_on: {{ ref(r) }}
{% endfor %}
-- From source to target by entity and period (spec §5.4): rows lost, extra and doubled; measure differences of
-- rows that stayed in their period; rows that moved to another period. Each period ends at the target.
{% set rows = load_config_rows() %}
{% set bounds = load_dataset_row() %}
with
measures as (
    {%- for cfg in rows %}
    {%- set measures = load_list(cfg['measures']) %}
    select '{{ cfg["entity"] }}' as entity, {{ ("'" ~ measures[0] ~ "'") if measures else 'null' }}::varchar as measure
    {%- if not loop.last %}
    union all
    {%- endif %}
    {%- else %}
    select null::varchar as entity, null::varchar as measure where false
    {%- endfor %}
),
found as (
    select * from {{ ref('load_discrepancies') }}
),
moved as (
    select entity, key, max(period_source) as period_source, max(period_target) as period_target,
           max(amount_source) as amount_source, max(amount_target) as amount_target
    from found
    where column_name is not null and period_source <> period_target
    group by entity, key
),
row_steps as (
    select entity, case when difference < 0 then period_source else period_target end as period, cause as label,
           sum(difference) as rows,
           sum(case when difference < 0 then -amount_source else amount_target end) as amount
    from found
    where column_name is null
    group by all
),
measure_steps as (
    select f.entity, f.period_source as period, f.cause as label, 0 as rows,
           sum(coalesce(f.amount_target, 0) - coalesce(f.amount_source, 0)) as amount
    from found as f
    join measures as m on m.entity = f.entity and m.measure = f.column_name
    where not exists (select 1 from moved where moved.entity = f.entity and moved.key = f.key)
    group by all
),
moved_steps as (
    select entity, period_source as period, 'moved_out' as label, -count(*) as rows, -sum(amount_source) as amount
    from moved group by all
    union all
    select entity, period_target as period, 'moved_in' as label, count(*) as rows, sum(amount_target) as amount
    from moved group by all
),
ends as (
    select entity, period, 'source' as label, source_rows as rows, source_amount as amount
    from {{ ref('load_totals') }}
    where {{ load_in_scope('period', bounds) }}
    union all
    select entity, period, 'target' as label, target_rows as rows, target_amount as amount
    from {{ ref('load_totals') }}
),
steps as (
    select * from ends
    union all select * from row_steps
    union all select * from measure_steps
    union all select * from moved_steps
)
select
    '{{ var("dataset") }}' as dataset, entity, period,
    case label
        when 'source' then 0
        when 'batch_boundary_loss' then 1 when 'missing_in_target' then 2 when 'deleted_left_behind' then 3
        when 'extra_in_target' then 4 when 'duplicate_after_rerun' then 5 when 'duplicate_in_target' then 6
        when 'truncated_decimal' then 7 when 'changed_not_exported' then 8 when 'value_mismatch' then 9
        when 'moved_out' then 10 when 'moved_in' then 11 when 'target' then 99
        else 50
    end as step,
    label, rows::bigint as rows, coalesce(amount, 0)::decimal(18, 4) as amount
from steps
