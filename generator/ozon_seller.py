"""Ozon seller, September 2026: accrual detail report, payout register, ledger, bank, truth.

The report layout (columns, ';', decimal comma, dd.mm.yyyy) and the payout schedule are the demo's
assumptions until checked against Ozon's documentation; README says which parts were confirmed.
Payouts: 16 Sep for 1-15 Sep, 1 Oct for 16-30 Sep (booked 2 Oct, in transit at month end).
"""
import datetime as dt
import random
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from generator.common import TRUTH_HEADER, Truth, days, money, truth_rows, write_csv

SEED = 20260902
POSTINGS = 400
TWO_UNIT_SHARE = 0.10
FULL_RETURNS = 27
PARTIAL_RETURNS = 3
COMMISSION = Decimal("0.15")
COMMISSION_OVERCHARGED = Decimal("0.17")
DUPLICATES = 2
MISSING_IN_LEDGER = 3
OVERCHARGED = 3
UNBOOKED_LOGISTICS = 2
STORAGE_DAYS = [dt.date(2026, 9, d) for d in (7, 14, 21, 28)]
UNBOOKED_STORAGE_DAYS = [dt.date(2026, 9, 14), dt.date(2026, 9, 28)]
FINE_DAYS = [dt.date(2026, 9, 10), dt.date(2026, 9, 24)]
UNBOOKED_FINE_DAY = dt.date(2026, 9, 24)
FINE = Decimal("-500.00")
FIRST_DAY = dt.date(2026, 9, 1)
LAST_DAY = dt.date(2026, 9, 30)
LAST_RETURN_SOURCE_DAY = dt.date(2026, 9, 25)
PAYOUTS = [
    ("P-2026-09-16", dt.date(2026, 9, 1), dt.date(2026, 9, 15), dt.date(2026, 9, 16), dt.date(2026, 9, 17)),
    ("P-2026-10-01", dt.date(2026, 9, 16), dt.date(2026, 9, 30), dt.date(2026, 10, 1), dt.date(2026, 10, 2)),
]
COUNTERPARTY = "OZON"
OTHER_BANK_ROWS = [(dt.date(2026, 9, 5), Decimal("-85000.00"), "Склад-Сервис", "Аренда склада, сентябрь")]

REPORT_HEADER = ["Дата начисления", "Тип начисления", "Номер отправления", "Артикул", "Количество", "Сумма итого, руб."]
PAYOUT_HEADER = ["Номер выплаты", "Период с", "Период по", "Дата выплаты", "Сумма, руб."]
LEDGER_HEADER = ["entry_id", "order_key", "date", "amount", "currency", "kind", "channel"]
BANK_HEADER = ["transaction_id", "booking_date", "amount", "currency", "counterparty", "reference"]


@dataclass
class Posting:
    number: str
    day: dt.date
    article: str
    units: int
    price: Decimal
    logistics: Decimal
    rate: Decimal = COMMISSION


def ru_amount(value: Decimal) -> str:
    return f"{value:.2f}".replace(".", ",")


def ru_day(day: dt.date) -> str:
    return day.strftime("%d.%m.%Y")


def generate(out: Path) -> None:
    rng = random.Random(SEED)
    september = days(FIRST_DAY, LAST_DAY)

    postings, numbers = [], set()
    while len(postings) < POSTINGS:
        number = f"{rng.randint(10_000_000, 99_999_999)}-{rng.randint(1000, 9999)}-1"
        if number in numbers:
            continue
        numbers.add(number)
        postings.append(Posting(
            number=number, day=rng.choice(september), article=f"NUT-{rng.randint(1, 50):03d}",
            units=2 if rng.random() < TWO_UNIT_SHARE else 1,
            price=money(Decimal(rng.randint(30000, 300000)) / 100),
            logistics=money(-Decimal(rng.randint(6000, 18000)) / 100),
        ))

    singles = [p for p in postings if p.units == 1]
    doubles = [p for p in postings if p.units == 2]
    rng.shuffle(singles)
    rng.shuffle(doubles)
    returned = [p for p in singles if p.day <= LAST_RETURN_SOURCE_DAY][:FULL_RETURNS]
    partial = [p for p in doubles if p.day <= LAST_RETURN_SOURCE_DAY][:PARTIAL_RETURNS]
    assert len(partial) == PARTIAL_RETURNS
    taken = {p.number for p in returned}
    rest = [p for p in singles if p.number not in taken]
    duplicated = rest[:DUPLICATES]
    missing = rest[DUPLICATES:DUPLICATES + MISSING_IN_LEDGER]
    overcharged = rest[DUPLICATES + MISSING_IN_LEDGER:DUPLICATES + MISSING_IN_LEDGER + OVERCHARGED]
    no_logistics = rest[DUPLICATES + MISSING_IN_LEDGER + OVERCHARGED:][:UNBOOKED_LOGISTICS]
    for p in overcharged:
        p.rate = COMMISSION_OVERCHARGED

    lines, ledger = [], []

    def line(day, kind, posting, amount, units=None):
        lines.append({"day": day, "type": kind, "posting": posting.number if posting else "",
                      "article": posting.article if posting else "", "units": units, "amount": amount})

    def book(day, key, amount, kind):
        ledger.append({"date": day, "key": key, "amount": amount, "kind": kind})

    for p in postings:
        for _ in range(p.units):
            line(p.day, "Продажа", p, p.price, 1)
            line(p.day, "Вознаграждение за продажу", p, -money(p.price * p.rate), 1)
            book(p.day, p.number, p.price, "sale")
            book(p.day, p.number, -money(p.price * COMMISSION), "fee")
        line(p.day, "Логистика", p, p.logistics)
        book(p.day, p.number, p.logistics, "charge")
    for p in returned + partial:
        day = p.day + dt.timedelta(days=rng.randint(1, 5))
        line(day, "Возврат", p, -p.price, 1)
        book(day, p.number, -p.price * p.units, "refund")
    for day in STORAGE_DAYS:
        amount = money(-Decimal(rng.randint(30000, 90000)) / 100)
        line(day, "Хранение", None, amount)
        book(day, f"storage:{day.isoformat()}", amount, "charge")
    for day in FINE_DAYS:
        line(day, "Штраф", None, FINE)
        book(day, f"fine:{day.isoformat()}", FINE, "charge")
    assert all(FIRST_DAY <= x["day"] <= LAST_DAY for x in lines)

    def entry(key: str, kind: str) -> dict:
        return next(e for e in ledger if e["key"] == key and e["kind"] == kind)

    truth = []
    for p in duplicated:
        ledger.append(dict(entry(p.number, "sale")))
        truth.append(Truth("operation", "duplicate", p.number, "sale", -p.price))
    for p in missing:
        ledger.remove(entry(p.number, "sale"))
        truth.append(Truth("operation", "missing_in_ledger", p.number, "sale", p.price))
    for p in overcharged:
        truth.append(Truth("operation", "fee", p.number, "fee",
                           -money(p.price * COMMISSION_OVERCHARGED) + money(p.price * COMMISSION)))
    for p in partial:
        truth.append(Truth("operation", "partial", p.number, "refund", -p.price + p.price * p.units))
    for p in no_logistics:
        ledger.remove(entry(p.number, "charge"))
        truth.append(Truth("operation", "unbooked", p.number, "charge", p.logistics))
    for day in UNBOOKED_STORAGE_DAYS:
        e = entry(f"storage:{day.isoformat()}", "charge")
        ledger.remove(e)
        truth.append(Truth("operation", "unbooked", e["key"], "charge", e["amount"]))
    fine = entry(f"fine:{UNBOOKED_FINE_DAY.isoformat()}", "charge")
    ledger.remove(fine)
    truth.append(Truth("operation", "unbooked", fine["key"], "charge", fine["amount"]))

    payouts = []
    for payout_id, start, end, paid_on, booked_on in PAYOUTS:
        amount = sum((x["amount"] for x in lines if start <= x["day"] <= end), Decimal("0.00"))
        payouts.append((payout_id, start, end, paid_on, booked_on, amount))
    last_id, *_, last_amount = payouts[-1]
    truth.append(Truth("bank", "in_transit", last_id, "payout", -last_amount))

    lines.sort(key=lambda x: (x["day"], x["posting"], x["type"], x["amount"]))
    report_rows = [[ru_day(x["day"]), x["type"], x["posting"], x["article"],
                    "" if x["units"] is None else x["units"], ru_amount(x["amount"])] for x in lines]
    payout_rows = [[pid, ru_day(s), ru_day(e), ru_day(paid), ru_amount(a)] for pid, s, e, paid, _, a in payouts]

    ledger.sort(key=lambda e: (e["date"], e["key"], e["kind"], e["amount"]))
    ledger_rows = [[f"JE-{n:05d}", e["key"], e["date"].isoformat(), f"{e['amount']:.2f}", "RUB", e["kind"], "ozon"]
                   for n, e in enumerate(ledger, start=1)]

    bank = [(booked, a, COUNTERPARTY, f"Перечисление средств по договору за период {ru_day(s)}–{ru_day(e)}")
            for _, s, e, _, booked, a in payouts] + OTHER_BANK_ROWS
    bank.sort(key=lambda b: (b[0], b[3]))
    bank_rows = [[f"BK-{n:05d}", day.isoformat(), f"{amount:.2f}", "RUB", party, reference]
                 for n, (day, amount, party, reference) in enumerate(bank, start=1)]

    write_csv(out / "ozon_report.csv", REPORT_HEADER, report_rows, delimiter=";")
    write_csv(out / "ozon_payouts.csv", PAYOUT_HEADER, payout_rows, delimiter=";")
    write_csv(out / "ledger.csv", LEDGER_HEADER, ledger_rows)
    write_csv(out / "bank.csv", BANK_HEADER, bank_rows)
    write_csv(out / "truth.csv", TRUTH_HEADER, truth_rows(truth))
