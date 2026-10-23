{{ config(enabled = var('suite', 'recon') == 'load' and var('dataset') == 'subscribe_co', tags = ['load_check']) }}
-- Card and bank times carry an offset; the old system stored manual payments in Helsinki local time without
-- one. Both become UTC explicitly, so the session time zone never changes a date. Unknown channels stop the build.
select
    payment_id,
    invoice_no,
    case channel
        when 'card' then timezone('UTC', paid_at::timestamptz)
        when 'bank' then timezone('UTC', paid_at::timestamptz)
        when 'manual' then timezone('UTC', timezone('Europe/Helsinki', paid_at::timestamp))
        else error('Unknown subscribe_co channel: ' || channel) end as paid_at,
    amount,
    channel
from read_csv('{{ data_file("legacy_payments.csv") }}', header = true, columns = {
    'payment_id': 'VARCHAR', 'invoice_no': 'VARCHAR', 'paid_at': 'VARCHAR', 'amount': 'DECIMAL(18,4)',
    'channel': 'VARCHAR'})
