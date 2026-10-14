{{ config(enabled = var('platform') == 'stripe') }}
with raw as (
    select * from read_csv('{{ data_file("stripe_payouts.csv") }}', header = true, columns = {
        'id': 'VARCHAR', 'amount': 'BIGINT', 'currency': 'VARCHAR', 'created': 'BIGINT',
        'arrival_date': 'BIGINT', 'status': 'VARCHAR'})
),
periods as (
    select
        automatic_payout_id as payout_id,
        min(cast(created_utc as date)) as period_from,
        max(cast(created_utc as date)) as period_to
    from {{ ref('stg_stripe__payout_items') }}
    group by automatic_payout_id
)
select
    raw.id as payout_id,
    cast(epoch_ms(raw.arrival_date * 1000) as date) as paid_on,
    periods.period_from,
    periods.period_to,
    cast(cast(raw.amount as decimal(18, 2)) * cast(0.01 as decimal(4, 2)) as decimal(18, 2)) as amount,
    upper(raw.currency) as currency
from raw
left join periods on periods.payout_id = raw.id
