{{ config(enabled = var('platform') == 'wb') }}
-- One report row carries several amounts; kind_map_wb names which of them become lines and with what sign.
-- The commission is ppvz_for_pay minus the retail price, so a sale gives retail and commission, never ppvz
-- as well. Rows without srid (storage, fines, deductions) are keyed '<code>:<date>', the key the books know.
-- A non-zero amount that the mapping does not cover for its operation stops the run, never goes missing.
with report as (
    select * from {{ ref('stg_wb__report') }}
),
map as (
    select * from {{ ref('kind_map_wb') }}
),
coverage as (
    select * from (values
        ('retail', 'retail_price_withdisc_rub'), ('commission', 'retail_price_withdisc_rub'),
        ('commission', 'ppvz_for_pay'), ('net', 'ppvz_for_pay'), ('delivery', 'delivery_rub'),
        ('storage', 'storage_fee'), ('penalty', 'penalty'), ('deduction', 'deduction')
    ) as c (part, money_column)
),
amounts as (
    unpivot (
        select rrd_id, supplier_oper_name, retail_price_withdisc_rub, ppvz_for_pay, delivery_rub,
               storage_fee, penalty, deduction
        from report
    )
    on retail_price_withdisc_rub, ppvz_for_pay, delivery_rub, storage_fee, penalty, deduction
    into name money_column value amount
),
unmapped as (
    select a.rrd_id, a.supplier_oper_name, a.money_column
    from amounts as a
    where a.amount <> 0
      and a.supplier_oper_name in (select supplier_oper_name from map)
      and not exists (
          select 1
          from map as m
          join coverage as c on c.part = m.part
          where m.supplier_oper_name = a.supplier_oper_name and c.money_column = a.money_column)
),
checked as (
    select report.*
    from report
    where case when report.rrd_id in (select rrd_id from unmapped)
               then error('Unmapped Wildberries amount in rrd_id ' || report.rrd_id || ': '
                          || (select string_agg(u.supplier_oper_name || '.' || u.money_column, ', ')
                              from unmapped as u where u.rrd_id = report.rrd_id))
               else true end
),
lines as (
    select
        checked.rrd_id || ':' || coalesce(map.part, 'unknown') as line_id,
        checked.realizationreport_id as payout_id,
        coalesce(checked.srid, map.code || ':' || strftime(checked.rr_dt, '%Y-%m-%d')) as key,
        case when map.kind is null
             then error('Unknown Wildberries operation: ' || checked.supplier_oper_name)
             else map.kind end as kind,
        cast(case when map.kind is null
                  then error('Unknown Wildberries operation: ' || checked.supplier_oper_name)
                  else map.sign * case map.part
                      when 'retail' then checked.retail_price_withdisc_rub
                      when 'commission' then checked.ppvz_for_pay - checked.retail_price_withdisc_rub
                      when 'net' then checked.ppvz_for_pay
                      when 'delivery' then checked.delivery_rub
                      when 'storage' then checked.storage_fee
                      when 'penalty' then checked.penalty
                      when 'deduction' then checked.deduction
                      else error('Unknown Wildberries amount part: ' || map.part)
                  end end as decimal(18, 2)) as amount,
        'RUB' as currency,
        checked.rr_dt as occurred_on,
        'RUB' as customer_currency
    from checked
    left join map on map.supplier_oper_name = checked.supplier_oper_name
)
select * from lines where amount <> 0
