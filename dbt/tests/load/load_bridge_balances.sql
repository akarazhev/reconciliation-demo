{{ config(enabled = var('suite', 'recon') == 'load', tags = ['load_check'], severity = 'error') }}
-- The bridge adds up (spec §5.4): source plus every step equals the target, in rows and to the cent.
with sums as (
    select dataset, entity, period,
           sum(case when label = 'target' then 0 else rows end) as rows_through,
           sum(case when label = 'target' then rows else 0 end) as rows_target,
           sum(case when label = 'target' then 0 else amount end) as amount_through,
           sum(case when label = 'target' then amount else 0 end) as amount_target
    from {{ ref('load_bridge') }}
    group by dataset, entity, period
)
select * from sums where rows_through <> rows_target or amount_through <> amount_target
