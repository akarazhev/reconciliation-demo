{{ config(enabled = var('suite', 'recon') == 'load' and var('dataset') == 'subscribe_co', tags = ['load_check']) }}
-- The new database keys customers by customer_id; the migration's key map brings back customer_no.
with customers as (
    select * from read_csv('{{ data_file("target_customers.csv") }}', header = true, columns = {
        'customer_id': 'VARCHAR', 'name': 'VARCHAR', 'country': 'VARCHAR', 'address_line1': 'VARCHAR',
        'address_line2': 'VARCHAR', 'created_at': 'TIMESTAMPTZ'})
),
key_map as (
    select * from read_csv('{{ data_file("key_map.csv") }}', header = true, columns = {
        'customer_no': 'VARCHAR', 'customer_id': 'VARCHAR'})
)
select
    case when key_map.customer_no is null
         then error('Unknown subscribe_co customer_id: ' || customers.customer_id)
         else key_map.customer_no end as customer_no,
    customers.name,
    customers.country,
    customers.address_line1,
    customers.address_line2,
    timezone('UTC', customers.created_at) as created_at
from customers
left join key_map on key_map.customer_id = customers.customer_id
