"""EU web shop paid through Stripe, the second month: September exactly as eu_shop, then October 2026.

October brings no new ordinary errors. What it plants sits on the month ends: a September USD charge refunded
on 6 October at the October rate and booked at the original amount (fx); a September dispute won on 14 October,
its amount returned and not booked, the dispute fee kept (unbooked); payouts in transit on 30 September and on
31 October. truth.csv holds October's discrepancies only: September's are carried over by the reconciliation.
"""
import datetime as dt
import random
from decimal import Decimal
from pathlib import Path

from generator import eu_shop
from generator.common import Truth, days, money, token
from generator.eu_shop import Month, Txn, stripe_fee

SEED = 20261001
CHARGES = 620
USD_SHARE = 0.10
EUR_TO_USD = Decimal("1.19")
REFUNDS = 20
FIRST_DAY = dt.date(2026, 10, 1)
LAST_DAY = dt.date(2026, 10, 31)
LAST_REFUND_SOURCE_DAY = dt.date(2026, 10, 20)
STATEMENT_END = dt.date(2026, 11, 7)
FX_REFUND_AT = dt.datetime(2026, 10, 6, 10, 41, 7)
DISPUTE_WON_AT = dt.datetime(2026, 10, 14, 9, 12, 30)
OTHER_BANK_ROWS = [
    (dt.date(2026, 10, 26), Decimal("-6150.00"), "Payroll", "Salaries October"),
    (dt.date(2026, 11, 2), Decimal("-2400.00"), "Office Rent GmbH", "Rent November"),
]


def generate(out: Path) -> None:
    september = eu_shop.september()
    rng = random.Random(SEED)
    october = days(FIRST_DAY, LAST_DAY)

    charges = []
    for n in range(CHARGES):
        usd = rng.random() < USD_SHARE
        gross = money(Decimal(rng.randint(1500, 40000)) / 100)
        created = dt.datetime.combine(rng.choice(october), dt.time()) + dt.timedelta(seconds=rng.randint(0, 86399))
        charges.append(Txn(
            txn_id="txn_" + token(rng), created=created, category="charge", gross=gross,
            fee=stripe_fee(gross, usd), source_id="ch_" + token(rng),
            order_id=f"EU-{10001 + eu_shop.CHARGES + n}",
            customer_amount=money(gross * EUR_TO_USD) if usd else gross,
            customer_currency="usd" if usd else "eur",
        ))

    eur = [c for c in charges if c.customer_currency == "eur"]
    rng.shuffle(eur)
    refunded = [c for c in eur if c.created.date() <= LAST_REFUND_SOURCE_DAY][:REFUNDS]
    refunds = []
    for c in refunded:
        created = c.created + dt.timedelta(days=rng.randint(1, 9), seconds=rng.randint(0, 3600))
        refunds.append(Txn("txn_" + token(rng), created, "refund", -c.gross, Decimal("0.00"),
                           "re_" + token(rng), c.order_id, -c.gross, c.customer_currency))

    # The customer gets back the dollars they paid; Stripe converts them at the rate of the refund day.
    paid = max(september.usd[eu_shop.FX:], key=lambda c: (c.gross, c.order_id))   # the largest clean one: visible
    returned = money(paid.customer_amount / EUR_TO_USD)
    fx_refund = Txn("txn_" + token(rng), FX_REFUND_AT, "refund", -returned, Decimal("0.00"), "re_" + token(rng),
                    paid.order_id, -paid.customer_amount, paid.customer_currency)
    # A won dispute returns its amount on the dispute itself; the dispute fee stays taken.
    lost = september.disputes[0]
    won = Txn("txn_" + token(rng), DISPUTE_WON_AT, "dispute_reversal", -lost.gross, Decimal("0.00"),
              lost.source_id, "", -lost.customer_amount, lost.customer_currency)

    txns = sorted(charges + refunds + [fx_refund, won], key=lambda t: (t.created, t.txn_id))
    assert all(FIRST_DAY <= t.created.date() <= LAST_DAY for t in txns)

    ends = [d for d in days(FIRST_DAY, eu_shop.payout_day(LAST_DAY)) if d.weekday() < 5]
    payouts = eu_shop.make_payouts(rng, txns, ends)

    by_order = {c.order_id: c for c in charges} | {paid.order_id: paid}
    ledger = []
    for t in txns:
        if t.category == "charge":
            ledger.append({"date": t.created.date(), "key": t.order_id, "amount": t.gross, "kind": "sale"})
            ledger.append({"date": t.created.date(), "key": t.order_id, "amount": -t.fee, "kind": "fee"})
        elif t.category == "refund":
            ledger.append({"date": t.created.date(), "key": t.order_id, "amount": -by_order[t.order_id].gross,
                           "kind": "refund"})

    arrived = next(p for p in september.payouts if p["arrival"] > eu_shop.LAST_DAY)
    truth = [
        Truth("operation", "fx", paid.order_id, "refund", fx_refund.gross + paid.gross),
        Truth("operation", "unbooked", won.source_id, "charge", won.net),
        Truth("bank", "in_transit", arrived["id"], "payout", arrived["amount"]),
    ]
    truth += [Truth("bank", "in_transit", p["id"], "payout", -p["amount"]) for p in payouts if p["arrival"] > LAST_DAY]

    month = Month(september.usd, september.disputes, september.txns + txns, september.payouts + payouts,
                  september.ledger + ledger, truth)
    bank = (eu_shop.payout_rows_in_bank(month.payouts, STATEMENT_END)
            + eu_shop.OTHER_BANK_ROWS + OTHER_BANK_ROWS)
    eu_shop.write(out, month, bank)
