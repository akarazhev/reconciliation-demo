{{ config(enabled = var('platform') == 'stripe') }}
-- One balance transaction becomes one line per part named in kind_map_stripe: a charge gives
-- a sale (gross) and a fee (minus fee); zero parts (a refund's fee) are dropped.
with items as (
    select * from {{ ref('stg_stripe__payout_items') }}
),
map as (
    select * from {{ ref('kind_map_stripe') }}
),
lines as (
    select
        items.balance_transaction_id || ':' || coalesce(map.part, 'unknown') as line_id,
        items.automatic_payout_id as payout_id,
        coalesce(items.order_id, items.source_id) as key,
        case when map.kind is null
             then error('Unknown Stripe reporting_category: ' || items.reporting_category)
             else map.kind end as kind,
        cast(case when map.kind is null
                  then error('Unknown Stripe reporting_category: ' || items.reporting_category)
                  else case map.part when 'gross' then items.gross
                           when 'fee' then -items.fee
                           else items.net end end as decimal(18, 2)) as amount,
        upper(items.currency) as currency,
        cast(items.created_utc as date) as occurred_on,
        upper(coalesce(items.customer_facing_currency, items.currency)) as customer_currency
    from items
    left join map on map.reporting_category = items.reporting_category
)
select * from lines where amount <> 0
