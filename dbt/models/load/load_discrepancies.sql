{{ config(enabled = var('suite', 'recon') == 'load', tags = ['load_check']) }}
{% for r in var('load_relations', []) %}-- depends_on: {{ ref(r) }}
{% endfor %}
-- Placeholder until the comparison lands: empty, with the key columns of the final table.
select
    cast(null as varchar) as dataset,
    cast(null as varchar) as entity,
    cast(null as varchar) as cause,
    cast(null as varchar) as key,
    cast(null as varchar) as column_name
where false
