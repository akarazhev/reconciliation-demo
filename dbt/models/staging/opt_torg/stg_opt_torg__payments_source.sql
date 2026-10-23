{{ config(enabled = var('suite', 'recon') == 'load' and var('dataset') == 'opt_torg', tags = ['load_check']) }}
-- number is the invoice number the payment names.
select
    payment_guid,
    invoice_guid,
    number,
    pay_date,
    amount
from read_csv('{{ data_file("source_payments.csv") }}', header = true, columns = {
    'payment_guid': 'VARCHAR', 'invoice_guid': 'VARCHAR', 'number': 'VARCHAR', 'pay_date': 'DATE',
    'amount': 'DECIMAL(18,4)'})
