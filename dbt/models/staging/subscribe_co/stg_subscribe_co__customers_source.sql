{{ config(enabled = var('suite', 'recon') == 'load' and var('dataset') == 'subscribe_co', tags = ['load_check']) }}
-- address_line2 is not trimmed: a value of one space is data, and the migration check looks for it.
select
    customer_no,
    name,
    country,
    address_line1,
    address_line2,
    timezone('UTC', created_at) as created_at
from read_csv('{{ data_file("legacy_customers.csv") }}', header = true, columns = {
    'customer_no': 'VARCHAR', 'name': 'VARCHAR', 'country': 'VARCHAR', 'address_line1': 'VARCHAR',
    'address_line2': 'VARCHAR', 'created_at': 'TIMESTAMPTZ'})
