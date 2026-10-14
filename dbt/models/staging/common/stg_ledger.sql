select
    '{{ var("dataset") }}' as dataset,
    entry_id,
    order_key as key,
    kind,
    amount,
    upper(currency) as currency,
    date as booked_on,
    channel
from read_csv('{{ data_file("ledger.csv") }}', header = true, columns = {
    'entry_id': 'VARCHAR', 'order_key': 'VARCHAR', 'date': 'DATE', 'amount': 'DECIMAL(18,2)',
    'currency': 'VARCHAR', 'kind': 'VARCHAR', 'channel': 'VARCHAR'})
