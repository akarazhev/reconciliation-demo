{{ config(enabled = var('platform') == 'stripe') }}
select
    balance_transaction_id,
    created_utc,
    available_on_utc,
    currency,
    gross,
    fee,
    net,
    reporting_category,
    source_id,
    automatic_payout_id,
    automatic_payout_effective_at,
    customer_facing_amount,
    customer_facing_currency,
    nullif(trim("payment_metadata[order_id]"), '') as order_id
from read_csv('{{ data_file("stripe_balance.csv") }}', header = true, columns = {
    'balance_transaction_id': 'VARCHAR', 'created_utc': 'TIMESTAMP', 'available_on_utc': 'TIMESTAMP',
    'currency': 'VARCHAR', 'gross': 'DECIMAL(18,2)', 'fee': 'DECIMAL(18,2)', 'net': 'DECIMAL(18,2)',
    'reporting_category': 'VARCHAR', 'source_id': 'VARCHAR', 'automatic_payout_id': 'VARCHAR',
    'automatic_payout_effective_at': 'TIMESTAMP', 'customer_facing_amount': 'DECIMAL(18,2)',
    'customer_facing_currency': 'VARCHAR', 'payment_metadata[order_id]': 'VARCHAR'})
