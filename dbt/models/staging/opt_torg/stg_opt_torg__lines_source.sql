{{ config(enabled = var('suite', 'recon') == 'load' and var('dataset') == 'opt_torg', tags = ['load_check']) }}
select
    line_guid,
    doc_guid,
    line_no,
    article,
    qty,
    price,
    amount
from read_csv('{{ data_file("source_lines.csv") }}', header = true, columns = {
    'line_guid': 'VARCHAR', 'doc_guid': 'VARCHAR', 'line_no': 'INTEGER', 'article': 'VARCHAR', 'qty': 'INTEGER',
    'price': 'DECIMAL(18,4)', 'amount': 'DECIMAL(18,4)'})
