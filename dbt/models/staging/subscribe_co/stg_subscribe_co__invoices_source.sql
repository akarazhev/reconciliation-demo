{{ config(enabled = var('suite', 'recon') == 'load' and var('dataset') == 'subscribe_co', tags = ['load_check']) }}
-- Status codes become the statuses the check expects; a code it does not know stops the build.
with invoices as (
    select * from read_csv('{{ data_file("legacy_invoices.csv") }}', header = true, columns = {
        'invoice_no': 'VARCHAR', 'customer_no': 'VARCHAR', 'issued_at': 'TIMESTAMPTZ', 'amount': 'DECIMAL(18,4)',
        'currency': 'VARCHAR', 'status_code': 'VARCHAR'})
),
codes as (
    select code, value from {{ ref('expected_codes') }}
    where dataset = 'subscribe_co' and entity = 'invoices' and column_name = 'status'
)
select
    invoices.invoice_no,
    invoices.customer_no,
    timezone('UTC', invoices.issued_at) as issued_at,
    invoices.amount,
    invoices.currency,
    case when codes.value is null
         then error('Unknown subscribe_co status_code: ' || coalesce(invoices.status_code, 'NULL'))
         else codes.value end as status
from invoices
left join codes on codes.code = invoices.status_code
