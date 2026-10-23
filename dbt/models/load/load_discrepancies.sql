{{ config(enabled = var('suite', 'recon') == 'load', tags = ['load_check']) }}
{% for r in var('load_relations', []) %}-- depends_on: {{ ref(r) }}
{% endfor %}
-- Every difference the load made, with its cause and a one-line explanation (spec §5.3).
select
    d.dataset, d.entity, d.cause, d.key, d.column_name, d.source_value, d.target_value, d.difference,
    d.period_source, d.period_target, d.amount_source, d.amount_target,
    {{ load_explanation('d.cause') }} as explanation
from (
    select * from {{ ref('load_key_diff') }}
    union all by name
    select * from {{ ref('load_value_diff') }}
) as d
