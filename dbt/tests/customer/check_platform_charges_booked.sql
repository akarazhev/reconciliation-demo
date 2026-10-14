{{ config(severity = 'warn') }}
-- No platform charge or fee is left unbooked or under-booked.
select * from {{ ref('discrepancies') }} where cause in ('unbooked', 'fee')
