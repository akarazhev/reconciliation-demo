{{ config(severity = 'warn') }}
select * from {{ ref('discrepancies') }} where cause = 'in_transit'
