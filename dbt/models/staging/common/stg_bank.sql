select
    '{{ var("dataset") }}' as dataset,
    transaction_id,
    booking_date,
    amount,
    upper(currency) as currency,
    counterparty,
    reference
from read_csv('{{ data_file("bank.csv") }}', header = true, columns = {
    'transaction_id': 'VARCHAR', 'booking_date': 'DATE', 'amount': 'DECIMAL(18,2)',
    'currency': 'VARCHAR', 'counterparty': 'VARCHAR', 'reference': 'VARCHAR'})
