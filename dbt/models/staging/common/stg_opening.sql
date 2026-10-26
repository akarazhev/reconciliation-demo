{{ config(enabled = var('opening', false)) }}
-- The opening list (demo 1, October): what last month's reconciliation left open at operation level, written by
-- opening.py from that month's output. A missing file fails the build: a roll-forward never starts from nothing.
select '{{ var("dataset") }}' as dataset, key, kind, cause, difference, month
from read_csv('{{ data_file("opening.csv") }}', header = true, columns = {
    'key': 'VARCHAR', 'kind': 'VARCHAR', 'cause': 'VARCHAR', 'difference': 'DECIMAL(18,2)', 'month': 'VARCHAR'})
