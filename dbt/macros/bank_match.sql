{# The bank level's matching rules (spec §5.3), one copy for bank_matches and unsettled_payouts so both decide
   "matched" the same way: the payout id in the reference first, then by amount within the window. Both methods
   require one candidate on each side; ambiguous references never fall back to amount matching. Emits the CTEs
   reference_candidates, candidates and matched (with helpers) over CTEs named `payouts` (payout_id, paid_on,
   amount) and `deposits` (deposit_id, booked_on, amount, reference). #}
{% macro bank_match_ctes() -%}
reference_candidates as (
    select p.payout_id, d.deposit_id
    from payouts as p
    join deposits as d on list_contains(regexp_extract_all(d.reference, '[A-Za-z0-9_-]+'), p.payout_id)
),
by_reference as (
    select payout_id, deposit_id
    from reference_candidates
    qualify count(*) over (partition by payout_id) = 1
        and count(*) over (partition by deposit_id) = 1
),
payouts_left as (
    select * from payouts where payout_id not in (select payout_id from reference_candidates)
),
deposits_left as (
    select * from deposits where deposit_id not in (select deposit_id from reference_candidates)
),
candidates as (
    select p.payout_id, d.deposit_id
    from payouts_left as p
    join deposits_left as d
      on d.amount = p.amount
     and d.booked_on - p.paid_on between 0 and {{ var('deposit_window_days') }}
),
payout_candidates as (
    select payout_id, count(*) as n from candidates group by payout_id
),
deposit_candidates as (
    select deposit_id, count(*) as n from candidates group by deposit_id
),
by_amount as (
    select c.payout_id, c.deposit_id
    from candidates as c
    join payout_candidates as pc on pc.payout_id = c.payout_id
    join deposit_candidates as dc on dc.deposit_id = c.deposit_id
    where pc.n = 1 and dc.n = 1
),
matched as (
    select * from by_reference
    union all
    select * from by_amount
)
{%- endmacro %}
