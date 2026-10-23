{{ config(enabled = var('suite', 'recon') == 'load', tags = ['load_check']) }}
{% for r in var('load_relations', []) %}-- depends_on: {{ ref(r) }}
{% endfor %}
-- Rows on one side only and keys the target holds more than once, for every entity of load_config.
{% set rows = load_config_rows() %}
{% set bounds = load_dataset_row() %}
{%- for cfg in rows %}
select * from ({{ compare_keys(rows, cfg, bounds) }})
{%- if not loop.last %}
union all by name
{%- endif %}
{%- else %}
{{ load_empty_diff() }}
{%- endfor %}
