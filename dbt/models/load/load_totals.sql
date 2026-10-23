{{ config(enabled = var('suite', 'recon') == 'load', tags = ['load_check']) }}
{% for r in var('load_relations', []) %}-- depends_on: {{ ref(r) }}
{% endfor %}
-- Rows and amounts on each side by entity and period, over the rows the comparison covers.
{% set rows = load_config_rows() %}
{% set bounds = load_dataset_row() %}
{%- for cfg in rows %}
select * from ({{ compare_totals(rows, cfg, bounds) }})
{%- if not loop.last %}
union all by name
{%- endif %}
{%- else %}
select null::varchar as dataset, null::varchar as entity, null::date as period, 0 as source_rows,
       0::decimal(18, 4) as source_amount, 0 as target_rows, 0::decimal(18, 4) as target_amount
where false
{%- endfor %}
