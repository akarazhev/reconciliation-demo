{{ config(enabled = var('suite', 'recon') == 'load', tags = ['load_check']) }}
{% for r in var('load_relations', []) %}-- depends_on: {{ ref(r) }}
{% endfor %}
-- What the generator planted, at the grain of load_discrepancies (spec §6).
select dataset, entity, cause, key, column_name, difference
from read_csv('{{ data_file("truth.csv") }}', header = true, columns = {
    'dataset': 'VARCHAR', 'entity': 'VARCHAR', 'cause': 'VARCHAR', 'key': 'VARCHAR', 'column_name': 'VARCHAR',
    'difference': 'DECIMAL(18,4)'})
