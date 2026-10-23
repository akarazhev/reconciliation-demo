{{ config(enabled = var('suite', 'recon') == 'load' and var('dataset') == 'subscribe_co', tags = ['load_check']) }}
with invoices as (
    select * from read_csv('{{ data_file("target_invoices.csv") }}', header = true, columns = {
        'invoice_no': 'VARCHAR', 'customer_id': 'VARCHAR', 'issued_at': 'TIMESTAMPTZ', 'amount': 'DECIMAL(18,2)',
        'currency': 'VARCHAR', 'status': 'VARCHAR'})
),
key_map as (
    select * from read_csv('{{ data_file("key_map.csv") }}', header = true, columns = {
        'customer_no': 'VARCHAR', 'customer_id': 'VARCHAR'})
)
select
    invoices.invoice_no,
    case when key_map.customer_no is null
         then error('Unknown subscribe_co customer_id: ' || invoices.customer_id)
         else key_map.customer_no end as customer_no,
    timezone('UTC', invoices.issued_at) as issued_at,
    invoices.amount,
    invoices.currency,
    invoices.status
from invoices
left join key_map on key_map.customer_id = invoices.customer_id
