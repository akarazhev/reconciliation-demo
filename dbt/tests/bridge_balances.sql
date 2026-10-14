with b as (
    select
        sum(case when row_type = 'total' and label = 'ledger' then amount else 0 end) as ledger,
        sum(case when row_type = 'total' and label = 'platform' then amount else 0 end) as platform,
        sum(case when row_type = 'total' and label = 'payouts' then amount else 0 end) as payouts,
        sum(case when row_type = 'total' and label = 'bank' then amount else 0 end) as bank,
        sum(case when row_type = 'cause' and level = 'operation' then amount else 0 end) as d_operation,
        sum(case when row_type = 'cause' and level = 'payout' then amount else 0 end) as d_payout,
        sum(case when row_type = 'cause' and level = 'bank' then amount else 0 end) as d_bank
    from {{ ref('bridge') }}
)
select * from b
where ledger + d_operation <> platform
   or platform + d_payout <> payouts
   or payouts + d_bank <> bank
