"""Wildberries seller, September 2026: realization report rows, weekly report register, ledger, bank, truth.

Rows use the field names of the seller API's realization report (reportDetailByPeriod, v5), written as CSV.
The documentation could not be read (dev.wildberries.ru refused the robot), so the field names, operation
types, the payment date and the payment reference are the demo's assumptions; README says so.

Real WB weeks run Monday to Sunday and cross months. Here the first report starts on 1 September and the
last ends on 30 September (paid 2 October, in transit at month end): one report is one payout of one month.
Money of a row, as the books see it: a sale is the retail price plus a commission of ppvz_for_pay minus
retail; a return withholds ppvz_for_pay (net); logistics, storage, fines and deductions are charges.
"""
import datetime as dt
import random
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from generator.common import TRUTH_HEADER, Truth, days, money, truth_rows, write_csv

SEED = 20260903
ORDERS = 450
RETURNS = 15
GROSS_RETURNS = 2
TARIFF = Decimal("0.20")
OVERCHARGED_RATE = Decimal("0.25")
DUPLICATES = 2
MISSING_IN_LEDGER = 2
OVERCHARGED = 3
UNBOOKED_LOGISTICS = 2
FIRST_DAY = dt.date(2026, 9, 1)
LAST_DAY = dt.date(2026, 9, 30)
LAST_RETURN_SOURCE_DAY = dt.date(2026, 9, 25)
REPORTS = [
    (dt.date(2026, 9, 1), dt.date(2026, 9, 6), dt.date(2026, 9, 8)),
    (dt.date(2026, 9, 7), dt.date(2026, 9, 13), dt.date(2026, 9, 15)),
    (dt.date(2026, 9, 14), dt.date(2026, 9, 20), dt.date(2026, 9, 22)),
    (dt.date(2026, 9, 21), dt.date(2026, 9, 27), dt.date(2026, 9, 29)),
    (dt.date(2026, 9, 28), dt.date(2026, 9, 30), dt.date(2026, 10, 2)),
]
FIRST_REPORT_ID = 512_600_001
FIRST_RRD_ID = 3_100_000_001
FINES = [(dt.date(2026, 9, 9), Decimal("500.00")), (dt.date(2026, 9, 23), Decimal("1000.00"))]
DEDUCTIONS = [(dt.date(2026, 9, 15), Decimal("2500.00")), (dt.date(2026, 9, 29), Decimal("1800.00"))]
UNBOOKED_SERVICES = ["storage:2026-09-20", "fine:2026-09-23", "deduction:2026-09-29"]
COUNTERPARTY = "WILDBERRIES"
OTHER_BANK_ROWS = [(dt.date(2026, 9, 3), Decimal("-42000.00"), "Склад-Сервис", "Аренда склада, сентябрь")]
ZERO = Decimal("0.00")

REPORT_HEADER = [
    "rrd_id", "realizationreport_id", "date_from", "date_to", "rr_dt", "srid", "nm_id", "sa_name",
    "doc_type_name", "supplier_oper_name", "quantity", "retail_price_withdisc_rub", "ppvz_for_pay",
    "delivery_rub", "storage_fee", "penalty", "deduction", "currency_name",
]
REGISTER_HEADER = ["realizationreport_id", "date_from", "date_to", "create_dt", "payment_date", "total_payable"]
LEDGER_HEADER = ["entry_id", "order_key", "date", "amount", "currency", "kind", "channel"]
BANK_HEADER = ["transaction_id", "booking_date", "amount", "currency", "counterparty", "reference"]


@dataclass
class Order:
    srid: str
    day: dt.date
    nm_id: int
    article: str
    price: Decimal
    logistics: Decimal
    rate: Decimal = TARIFF

    @property
    def for_pay(self) -> Decimal:
        return self.price - money(self.price * self.rate)


def report_index(day: dt.date) -> int:
    return next(n for n, (first, last, _) in enumerate(REPORTS) if first <= day <= last)


def generate(out: Path) -> None:
    rng = random.Random(SEED)
    september = days(FIRST_DAY, LAST_DAY)

    orders, seen = [], set()
    while len(orders) < ORDERS:
        srid = f"wb{rng.randint(10**11, 10**12 - 1)}"
        if srid in seen:
            continue
        seen.add(srid)
        orders.append(Order(
            srid=srid, day=rng.choice(september), nm_id=rng.randint(100_000_000, 999_999_999),
            article=f"HOME-{rng.randint(1, 60):03d}", price=money(Decimal(rng.randint(40000, 450000)) / 100),
            logistics=money(Decimal(rng.randint(5000, 15000)) / 100),
        ))

    shuffled = orders[:]
    rng.shuffle(shuffled)
    returned = [o for o in shuffled if o.day <= LAST_RETURN_SOURCE_DAY][:RETURNS]
    booked_gross = {o.srid for o in returned[:GROSS_RETURNS]}
    taken = {o.srid for o in returned}
    rest = [o for o in shuffled if o.srid not in taken]
    duplicated = rest[:DUPLICATES]
    missing = rest[DUPLICATES:DUPLICATES + MISSING_IN_LEDGER]
    overcharged = rest[DUPLICATES + MISSING_IN_LEDGER:DUPLICATES + MISSING_IN_LEDGER + OVERCHARGED]
    no_logistics = rest[DUPLICATES + MISSING_IN_LEDGER + OVERCHARGED:][:UNBOOKED_LOGISTICS]
    for o in overcharged:
        o.rate = OVERCHARGED_RATE

    rows, ledger = [], []

    def row(day, oper, order=None, doc="", quantity=0, retail=ZERO, for_pay=ZERO,
            delivery=ZERO, storage=ZERO, penalty=ZERO, deduction=ZERO):
        rows.append({"day": day, "oper": oper, "srid": order.srid if order else "",
                     "nm_id": order.nm_id if order else "", "article": order.article if order else "",
                     "doc": doc, "quantity": quantity, "retail": retail, "for_pay": for_pay,
                     "delivery": delivery, "storage": storage, "penalty": penalty, "deduction": deduction})

    def book(day, key, amount, kind):
        ledger.append({"date": day, "key": key, "amount": amount, "kind": kind})

    for o in orders:
        row(o.day, "Продажа", o, "Продажа", 1, o.price, o.for_pay)
        row(o.day, "Логистика", o, delivery=o.logistics)
        book(o.day, o.srid, o.price, "sale")
        book(o.day, o.srid, -money(o.price * TARIFF), "fee")
        book(o.day, o.srid, -o.logistics, "charge")
    for o in returned:
        day = o.day + dt.timedelta(days=rng.randint(1, 5))
        back = money(Decimal(rng.randint(5000, 15000)) / 100)
        row(day, "Возврат", o, "Возврат", 1, o.price, o.for_pay)
        row(day, "Логистика", o, delivery=back)
        book(day, o.srid, -o.price if o.srid in booked_gross else -o.for_pay, "refund")
        book(day, o.srid, -back, "charge")
    services = [(last, "Хранение", "storage", money(Decimal(rng.randint(40000, 120000)) / 100))
                for _, last, _ in REPORTS]
    services += [(day, "Штраф", "fine", amount) for day, amount in FINES]
    services += [(day, "Удержание", "deduction", amount) for day, amount in DEDUCTIONS]
    column = {"Хранение": "storage", "Штраф": "penalty", "Удержание": "deduction"}
    for day, oper, code, amount in services:
        row(day, oper, **{column[oper]: amount})
        book(day, f"{code}:{day.isoformat()}", -amount, "charge")
    assert all(FIRST_DAY <= r["day"] <= LAST_DAY for r in rows)

    def entry(key: str, kind: str) -> dict:
        return next(e for e in ledger if e["key"] == key and e["kind"] == kind)

    truth = []
    for o in duplicated:
        ledger.append(dict(entry(o.srid, "sale")))
        truth.append(Truth("operation", "duplicate", o.srid, "sale", -o.price))
    for o in missing:
        ledger.remove(entry(o.srid, "sale"))
        truth.append(Truth("operation", "missing_in_ledger", o.srid, "sale", o.price))
    for o in overcharged:
        truth.append(Truth("operation", "fee", o.srid, "fee",
                           -money(o.price * OVERCHARGED_RATE) + money(o.price * TARIFF)))
    for o in returned[:GROSS_RETURNS]:
        truth.append(Truth("operation", "partial", o.srid, "refund", o.price - o.for_pay))
    for o in no_logistics:
        ledger.remove(entry(o.srid, "charge"))
        truth.append(Truth("operation", "unbooked", o.srid, "charge", -o.logistics))
    for key in UNBOOKED_SERVICES:
        e = entry(key, "charge")
        ledger.remove(e)
        truth.append(Truth("operation", "unbooked", key, "charge", e["amount"]))

    totals = [ZERO for _ in REPORTS]
    for r in rows:
        sign = {"Продажа": 1, "Возврат": -1}.get(r["oper"], 0)
        totals[report_index(r["day"])] += (sign * r["for_pay"] - r["delivery"] - r["storage"]
                                           - r["penalty"] - r["deduction"])
    last = len(REPORTS) - 1
    truth.append(Truth("bank", "in_transit", str(FIRST_REPORT_ID + last), "payout", -totals[last]))

    rows.sort(key=lambda r: (r["day"], r["srid"], r["oper"]))
    report_rows = []
    for n, r in enumerate(rows):
        i = report_index(r["day"])
        first, last_day, _ = REPORTS[i]
        report_rows.append([
            FIRST_RRD_ID + n, FIRST_REPORT_ID + i, first.isoformat(), last_day.isoformat(), r["day"].isoformat(),
            r["srid"], r["nm_id"], r["article"], r["doc"], r["oper"], r["quantity"], f"{r['retail']:.2f}",
            f"{r['for_pay']:.2f}", f"{r['delivery']:.2f}", f"{r['storage']:.2f}", f"{r['penalty']:.2f}",
            f"{r['deduction']:.2f}", "руб",
        ])
    register_rows = [[FIRST_REPORT_ID + i, first.isoformat(), last_day.isoformat(),
                      (last_day + dt.timedelta(1)).isoformat(), paid.isoformat(), f"{totals[i]:.2f}"]
                     for i, (first, last_day, paid) in enumerate(REPORTS)]

    ledger.sort(key=lambda e: (e["date"], e["key"], e["kind"], e["amount"]))
    ledger_rows = [[f"JE-{n:05d}", e["key"], e["date"].isoformat(), f"{e['amount']:.2f}", "RUB", e["kind"], "wb"]
                   for n, e in enumerate(ledger, start=1)]

    bank = [(paid, totals[i], COUNTERPARTY,
             f"Оплата по отчёту о реализации № {FIRST_REPORT_ID + i} за период "
             f"{first:%d.%m.%Y}–{last_day:%d.%m.%Y}")
            for i, (first, last_day, paid) in enumerate(REPORTS)] + OTHER_BANK_ROWS
    bank.sort(key=lambda b: (b[0], b[3]))
    bank_rows = [[f"BK-{n:05d}", day.isoformat(), f"{amount:.2f}", "RUB", party, reference]
                 for n, (day, amount, party, reference) in enumerate(bank, start=1)]

    write_csv(out / "wb_report.csv", REPORT_HEADER, report_rows)
    write_csv(out / "wb_reports.csv", REGISTER_HEADER, register_rows)
    write_csv(out / "ledger.csv", LEDGER_HEADER, ledger_rows)
    write_csv(out / "bank.csv", BANK_HEADER, bank_rows)
    write_csv(out / "truth.csv", TRUTH_HEADER, truth_rows(truth))
