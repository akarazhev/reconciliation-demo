select '{{ var("dataset") }}' as dataset, level, cause, key, kind, difference
from read_csv('{{ data_file("truth.csv") }}', header = true, columns = {
    'level': 'VARCHAR', 'cause': 'VARCHAR', 'key': 'VARCHAR', 'kind': 'VARCHAR', 'difference': 'DECIMAL(18,2)'})
