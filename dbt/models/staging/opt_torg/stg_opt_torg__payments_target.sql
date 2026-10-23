{{ config(enabled = var('suite', 'recon') == 'load' and var('dataset') == 'opt_torg', tags = ['load_check']) }}
select
    target.payment_guid,
    target.invoice_guid,
    target.number,
    target.pay_date,
    target.amount,
    target.export_night,
    target.export_run,
    exports.exported_at
from read_csv('{{ data_file("target_payments.csv") }}', header = true, columns = {
    'payment_guid': 'VARCHAR', 'invoice_guid': 'VARCHAR', 'number': 'VARCHAR', 'pay_date': 'DATE',
    'amount': 'DECIMAL(18,2)', 'export_night': 'DATE', 'export_run': 'INTEGER'}) as target
left join {{ ref('stg_opt_torg__exports') }} as exports
  on exports.export_night = target.export_night and exports.export_run = target.export_run
