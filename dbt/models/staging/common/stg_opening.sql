-- The opening list (demo 1, October): what last month's reconciliation left open, written by opening.py from that
-- month's output: operation lines, and payouts not yet in the bank. A missing file fails the build: a roll-forward
-- never starts from nothing. Without an opening (var opening) the list is empty, so bank_matches can always read it.
{% if var('opening', false) %}
select '{{ var("dataset") }}' as dataset, level, key, kind, cause, difference, month
from read_csv('{{ data_file("opening.csv") }}', header = true, columns = {
    'level': 'VARCHAR', 'key': 'VARCHAR', 'kind': 'VARCHAR', 'cause': 'VARCHAR', 'difference': 'DECIMAL(18,2)',
    'month': 'VARCHAR'})
{% else %}
select '{{ var("dataset") }}' as dataset, cast(null as varchar) as level, cast(null as varchar) as key,
       cast(null as varchar) as kind, cast(null as varchar) as cause, cast(null as decimal(18, 2)) as difference,
       cast(null as varchar) as month
where false
{% endif %}
