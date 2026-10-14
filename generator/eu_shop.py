"""EU web shop paid through Stripe, September 2026.

Writes stripe_balance.csv (Itemized payout reconciliation), stripe_payouts.csv (Payout objects),
ledger.csv, bank.csv and truth.csv: clean books first, then the planted discrepancies, each
recorded in truth.csv. One payout per weekday; weekend operations go to Monday's payout.
"""
import datetime as dt
import random
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from generator.common import TRUTH_HEADER, Truth, days, money, token, truth_rows, write_csv

SEED = 20260901
CHARGES = 600
USD_SHARE = 0.10
EUR_TO_USD = Decimal("1.17")
REFUNDS = 20
PARTIAL_REFUNDS = 2
PARTIAL_SHARE = Decimal("0.40")
DISPUTES = 2
DISPUTE_FEE = Decimal("15.00")
DUPLICATES = 3
MISSING_IN_LEDGER = 3
UNBOOKED_FEES = 3
FX = 2
FX_BOOKED_SKEW = Decimal("1.02")
MISMATCHES = [(Decimal("129.00"), Decimal("192.00")), (Decimal("345.60"), Decimal("354.60"))]
FIRST_DAY = dt.date(2026, 9, 1)
LAST_DAY = dt.date(2026, 9, 30)
LAST_REFUND_SOURCE_DAY = dt.date(2026, 9, 20)
STATEMENT_END = dt.date(2026, 10, 7)
COUNTERPARTY = "STRIPE"
OTHER_BANK_ROWS = [
    (dt.date(2026, 9, 1), Decimal("-2400.00"), "Office Rent GmbH", "Rent September"),
    (dt.date(2026, 9, 25), Decimal("-6150.00"), "Payroll", "Salaries September"),
    (dt.date(2026, 10, 1), Decimal("-2400.00"), "Office Rent GmbH", "Rent October"),
]

BALANCE_HEADER = [
    "balance_transaction_id", "created_utc", "available_on_utc", "currency", "gross", "fee", "net",
    "reporting_category", "source_id", "automatic_payout_id", "automatic_payout_effective_at",
    "customer_facing_amount", "customer_facing_currency", "payment_metadata[order_id]",
]
PAYOUT_HEADER = ["id", "amount", "currency", "created", "arrival_date", "status"]
LEDGER_HEADER = ["entry_id", "order_key", "date", "amount", "currency", "kind", "channel"]
BANK_HEADER = ["transaction_id", "booking_date", "amount", "currency", "counterparty", "reference"]


@dataclass
class Txn:
    txn_id: str
    created: dt.datetime
    category: str
    gross: Decimal
    fee: Decimal
    source_id: str
    order_id: str
    customer_amount: Decimal
    customer_currency: str
    payout_id: str = ""
    available_on: dt.datetime | None = None
    effective_at: dt.datetime | None = None

    @property
    def net(self) -> Decimal:
        return self.gross - self.fee


def stripe_fee(gross: Decimal, usd: bool) -> Decimal:
    rate = Decimal("0.0325") if usd else Decimal("0.015")
    return money(gross * rate + Decimal("0.25"))


def next_weekday(day: dt.date) -> dt.date:
    day += dt.timedelta(1)
    while day.weekday() >= 5:
        day += dt.timedelta(1)
    return day


def payout_day(day: dt.date) -> dt.date:
    while day.weekday() >= 5:
        day += dt.timedelta(1)
    return day


def epoch(day: dt.date, time: dt.time) -> int:
    return int(dt.datetime.combine(day, time, tzinfo=dt.UTC).timestamp())


def stamp(moment: dt.datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def generate(out: Path) -> None:
    rng = random.Random(SEED)
    september = days(FIRST_DAY, LAST_DAY)

    charges = []
    for n in range(CHARGES):
        usd = rng.random() < USD_SHARE
        gross = money(Decimal(rng.randint(1500, 40000)) / 100)
        created = dt.datetime.combine(rng.choice(september), dt.time()) + dt.timedelta(seconds=rng.randint(0, 86399))
        charges.append(Txn(
            txn_id="txn_" + token(rng), created=created, category="charge", gross=gross,
            fee=stripe_fee(gross, usd), source_id="ch_" + token(rng), order_id=f"EU-{10001 + n}",
            customer_amount=money(gross * EUR_TO_USD) if usd else gross,
            customer_currency="usd" if usd else "eur",
        ))

    eur = [c for c in charges if c.customer_currency == "eur"]
    usd = [c for c in charges if c.customer_currency == "usd"]
    rng.shuffle(eur)
    early = [c for c in eur if c.created.date() <= LAST_REFUND_SOURCE_DAY]
    refunded = early[:REFUNDS]
    disputed = early[REFUNDS:REFUNDS + DISPUTES]
    taken = {c.order_id for c in refunded + disputed}
    rest = [c for c in eur if c.order_id not in taken]
    duplicated = rest[:DUPLICATES]
    missing = rest[DUPLICATES:DUPLICATES + MISSING_IN_LEDGER]
    fee_unbooked = rest[DUPLICATES + MISSING_IN_LEDGER:DUPLICATES + MISSING_IN_LEDGER + UNBOOKED_FEES]
    mismatched = rest[DUPLICATES + MISSING_IN_LEDGER + UNBOOKED_FEES:][:len(MISMATCHES)]
    fx = usd[:FX]
    for charge, (platform_amount, _) in zip(mismatched, MISMATCHES, strict=True):
        charge.gross = platform_amount
        charge.fee = stripe_fee(platform_amount, usd=False)
        charge.customer_amount = platform_amount

    partial = {c.order_id for c in refunded[:PARTIAL_REFUNDS]}
    refunds = []
    for c in refunded:
        amount = money(c.gross * PARTIAL_SHARE) if c.order_id in partial else c.gross
        created = c.created + dt.timedelta(days=rng.randint(1, 9), seconds=rng.randint(0, 3600))
        refunds.append(Txn("txn_" + token(rng), created, "refund", -amount, Decimal("0.00"),
                           "re_" + token(rng), c.order_id, -amount, c.customer_currency))
    disputes = []
    for c in disputed:
        created = c.created + dt.timedelta(days=rng.randint(3, 8), seconds=rng.randint(0, 3600))
        disputes.append(Txn("txn_" + token(rng), created, "dispute", -c.gross, DISPUTE_FEE,
                            "du_" + token(rng), "", -c.gross, c.customer_currency))

    txns = sorted(charges + refunds + disputes, key=lambda t: (t.created, t.txn_id))
    assert all(FIRST_DAY <= t.created.date() <= LAST_DAY for t in txns)

    payouts = []
    for end in [d for d in september if d.weekday() < 5]:
        items = [t for t in txns if payout_day(t.created.date()) == end]
        payout_id = "po_" + token(rng, 24)
        arrival = next_weekday(end)
        for t in items:
            t.payout_id = payout_id
            t.available_on = dt.datetime.combine(end, dt.time(23, 59, 59))
            t.effective_at = dt.datetime.combine(arrival, dt.time())
        payouts.append({"id": payout_id, "end": end, "arrival": arrival,
                        "amount": sum((t.net for t in items), Decimal("0.00"))})
    in_transit = [p for p in payouts if p["arrival"] > LAST_DAY]
    assert len(in_transit) == 1

    by_order = {c.order_id: c for c in charges}
    ledger = []
    for t in txns:
        if t.category == "charge":
            ledger.append({"date": t.created.date(), "key": t.order_id, "amount": t.gross, "kind": "sale"})
            ledger.append({"date": t.created.date(), "key": t.order_id, "amount": -t.fee, "kind": "fee"})
        elif t.category == "refund":
            booked = -by_order[t.order_id].gross
            ledger.append({"date": t.created.date(), "key": t.order_id, "amount": booked, "kind": "refund"})

    def entry(order_id: str, kind: str) -> dict:
        return next(e for e in ledger if e["key"] == order_id and e["kind"] == kind)

    truth = []
    for c in duplicated:
        ledger.append(dict(entry(c.order_id, "sale")))
        truth.append(Truth("operation", "duplicate", c.order_id, "sale", -c.gross))
    for c in missing:
        ledger.remove(entry(c.order_id, "sale"))
        truth.append(Truth("operation", "missing_in_ledger", c.order_id, "sale", c.gross))
    for c in fee_unbooked:
        ledger.remove(entry(c.order_id, "fee"))
        truth.append(Truth("operation", "fee", c.order_id, "fee", -c.fee))
    for c in fx:
        booked = money(c.gross * FX_BOOKED_SKEW)
        entry(c.order_id, "sale")["amount"] = booked
        truth.append(Truth("operation", "fx", c.order_id, "sale", c.gross - booked))
    for c, (platform_amount, booked) in zip(mismatched, MISMATCHES, strict=True):
        entry(c.order_id, "sale")["amount"] = booked
        truth.append(Truth("operation", "amount_mismatch", c.order_id, "sale", platform_amount - booked))
    for r in refunds:
        if r.order_id in partial:
            truth.append(Truth("operation", "partial", r.order_id, "refund", r.gross + by_order[r.order_id].gross))
    for d in disputes:
        truth.append(Truth("operation", "unbooked", d.source_id, "charge", d.net))
    truth.append(Truth("bank", "in_transit", in_transit[0]["id"], "payout", -in_transit[0]["amount"]))

    ledger.sort(key=lambda e: (e["date"], e["key"], e["kind"], e["amount"]))
    ledger_rows = [[f"JE-{n:05d}", e["key"], e["date"].isoformat(), f"{e['amount']:.2f}", "EUR", e["kind"], "stripe"]
                   for n, e in enumerate(ledger, start=1)]

    bank = [(p["arrival"], p["amount"], COUNTERPARTY, f"STRIPE PAYOUT {p['id']}")
            for p in payouts if p["arrival"] <= STATEMENT_END] + OTHER_BANK_ROWS
    bank.sort(key=lambda b: (b[0], b[3]))
    bank_rows = [[f"BK-{n:05d}", day.isoformat(), f"{amount:.2f}", "EUR", party, reference]
                 for n, (day, amount, party, reference) in enumerate(bank, start=1)]

    balance_rows = [[
        t.txn_id, stamp(t.created), stamp(t.available_on), "eur", f"{t.gross:.2f}", f"{t.fee:.2f}", f"{t.net:.2f}",
        t.category, t.source_id, t.payout_id, stamp(t.effective_at), f"{t.customer_amount:.2f}",
        t.customer_currency, t.order_id,
    ] for t in txns]
    payout_rows = [[p["id"], int(p["amount"] * 100), "eur", epoch(p["end"], dt.time(23, 59, 59)),
                    epoch(p["arrival"], dt.time()), "paid"] for p in payouts]

    write_csv(out / "stripe_balance.csv", BALANCE_HEADER, balance_rows)
    write_csv(out / "stripe_payouts.csv", PAYOUT_HEADER, payout_rows)
    write_csv(out / "ledger.csv", LEDGER_HEADER, ledger_rows)
    write_csv(out / "bank.csv", BANK_HEADER, bank_rows)
    write_csv(out / "truth.csv", TRUTH_HEADER, truth_rows(truth))
