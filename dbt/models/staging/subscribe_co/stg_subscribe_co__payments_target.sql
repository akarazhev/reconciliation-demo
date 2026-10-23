{{ config(enabled = var('suite', 'recon') == 'load' and var('dataset') == 'subscribe_co', tags = ['load_check']) }}
select
    payment_id,
    invoice_no,
    timezone('UTC', paid_at) as paid_at,
    amount,
    channel,
    batch_no
from read_csv('{{ data_file("target_payments.csv") }}', header = true, columns = {
    'payment_id': 'VARCHAR', 'invoice_no': 'VARCHAR', 'paid_at': 'TIMESTAMPTZ', 'amount': 'DECIMAL(18,2)',
    'channel': 'VARCHAR', 'batch_no': 'INTEGER'})
