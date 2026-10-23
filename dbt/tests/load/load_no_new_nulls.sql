{{ config(enabled = var('suite', 'recon') == 'load', tags = ['load_check'], severity = 'warn') }}
{% for r in var('load_relations', []) %}-- depends_on: {{ ref(r) }}
{% endfor %}
-- The customer's check: no column has more NULLs in the target than in the source.
{% set rows = load_config_rows() %}
{% set bounds = load_dataset_row() %}
with profile as (
    {%- for cfg in rows %}
    select * from ({{ compare_nulls(rows, cfg, bounds) }})
    {%- if not loop.last %}
    union all
    {%- endif %}
    {%- else %}
    select null::varchar as dataset, null::varchar as entity, null::varchar as column_name, 0 as source_nulls,
           0 as target_nulls
    where false
    {%- endfor %}
)
select * from profile where target_nulls > source_nulls
