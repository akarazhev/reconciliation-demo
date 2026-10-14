{{ config(enabled = var('platform') == 'wb') }}
-- One report row carries several amounts; kind_map_wb names which of them become lines and with what sign.
-- The commission is ppvz_for_pay minus the retail price, so a sale gives retail and commission, never ppvz
-- as well. Rows without srid (storage, fines, deductions) are keyed '<code>:<date>', the key the books know.
with report as (
    select * from {{ ref('stg_wb__report') }}
),
map as (
    select * from {{ ref('kind_map_wb') }}
),
lines as (
    select
        report.rrd_id || ':' || coalesce(map.part, 'unknown') as line_id,
        report.realizationreport_id as payout_id,
        coalesce(report.srid, map.code || ':' || strftime(report.rr_dt, '%Y-%m-%d')) as key,
        case when map.kind is null
             then error('Unknown Wildberries operation: ' || report.supplier_oper_name)
             else map.kind end as kind,
        cast(case when map.kind is null
                  then error('Unknown Wildberries operation: ' || report.supplier_oper_name)
                  else map.sign * case map.part
                      when 'retail' then report.retail_price_withdisc_rub
                      when 'commission' then report.ppvz_for_pay - report.retail_price_withdisc_rub
                      when 'net' then report.ppvz_for_pay
                      when 'delivery' then report.delivery_rub
                      when 'storage' then report.storage_fee
                      when 'penalty' then report.penalty
                      when 'deduction' then report.deduction
                      else error('Unknown Wildberries amount part: ' || map.part)
                  end end as decimal(18, 2)) as amount,
        'RUB' as currency,
        report.rr_dt as occurred_on,
        'RUB' as customer_currency
    from report
    left join map on map.supplier_oper_name = report.supplier_oper_name
)
select * from lines where amount <> 0
