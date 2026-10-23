{{ config(enabled = var('suite', 'recon') == 'load' and var('dataset') == 'opt_torg', tags = ['load_check']) }}
-- The lines table has no unique key: a re-run writes a second copy of a line.
select
    target.line_guid,
    target.doc_guid,
    target.line_no,
    target.article,
    target.qty,
    target.price,
    target.amount,
    target.export_night,
    target.export_run,
    exports.exported_at
from read_csv('{{ data_file("target_lines.csv") }}', header = true, columns = {
    'line_guid': 'VARCHAR', 'doc_guid': 'VARCHAR', 'line_no': 'INTEGER', 'article': 'VARCHAR', 'qty': 'INTEGER',
    'price': 'DECIMAL(18,2)', 'amount': 'DECIMAL(18,2)', 'export_night': 'DATE', 'export_run': 'INTEGER'}) as target
left join {{ ref('stg_opt_torg__exports') }} as exports
  on exports.export_night = target.export_night and exports.export_run = target.export_run
