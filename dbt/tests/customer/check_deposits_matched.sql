{{ config(severity = 'warn') }}
-- Every platform deposit is matched with a payout; a date shift is reported by check_in_transit.
select * from {{ ref('discrepancies') }} where level = 'bank' and cause <> 'in_transit'
