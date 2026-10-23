{{ config(enabled = var('suite', 'recon') == 'load' and var('dataset') == 'opt_torg', tags = ['load_check']) }}
-- MySQL also holds last September's invoices from earlier exports; their runs are not in export_runs.
select
    target.doc_guid,
    target.number,
    target.doc_date,
    target.customer_inn,
    target.total,
    target.export_night,
    target.export_run,
    exports.exported_at
from read_csv('{{ data_file("target_invoices.csv") }}', header = true, columns = {
    'doc_guid': 'VARCHAR', 'number': 'VARCHAR', 'doc_date': 'DATE', 'customer_inn': 'VARCHAR',
    'total': 'DECIMAL(18,2)', 'export_night': 'DATE', 'export_run': 'INTEGER'}) as target
left join {{ ref('stg_opt_torg__exports') }} as exports
  on exports.export_night = target.export_night and exports.export_run = target.export_run
