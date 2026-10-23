{{ config(enabled = var('suite', 'recon') == 'load', tags = ['load_check']) }}
{% for r in var('load_relations', []) %}-- depends_on: {{ ref(r) }}
{% endfor %}
-- Values that differ on keys present on both sides, one row per column, for every entity of load_config.
{% set codes = ref('expected_codes') %}
{% set rows = load_config_rows() %}
{% set bounds = load_dataset_row() %}
{%- for cfg in rows %}
select * from ({{ compare_rows(rows, cfg, bounds, codes) }})
{%- if not loop.last %}
union all by name
{%- endif %}
{%- else %}
{{ load_empty_diff() }}
{%- endfor %}
