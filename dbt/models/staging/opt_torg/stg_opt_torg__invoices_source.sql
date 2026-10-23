{{ config(enabled = var('suite', 'recon') == 'load' and var('dataset') == 'opt_torg', tags = ['load_check']) }}
select
    doc_guid,
    number,
    doc_date,
    customer_inn,
    total,
    timezone('UTC', modified_at) as modified_at
from read_csv('{{ data_file("source_invoices.csv") }}', header = true, columns = {
    'doc_guid': 'VARCHAR', 'number': 'VARCHAR', 'doc_date': 'DATE', 'customer_inn': 'VARCHAR',
    'total': 'DECIMAL(18,4)', 'modified_at': 'TIMESTAMPTZ'})
