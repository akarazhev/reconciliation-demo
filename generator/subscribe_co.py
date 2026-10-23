"""A made-up subscription company moves its billing to a new database: customers, invoices and payments of
July to September 2026, once, on 30 September, in batches of 500 payments ordered by paid_at.

Writes the old database (legacy_*.csv), the new one after the move (target_*.csv), the two maps the move used
(status_map.csv without code H, key_map.csv) and truth.csv: clean data first, then the move as it went, every
damaged row recorded in truth.csv. Invoice amounts in the old database have four decimals; manual payments keep
the Helsinki local time without an offset, the way the old system stored them.
"""
import datetime as dt
import random
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from generator.common import money, token, write_csv
from generator.load_common import LOAD_TRUTH_HEADER, LoadTruth, load_truth_rows

SEED = 20260701
DATASET = "subscribe_co"
CUSTOMERS = 1200
MONTHS = (7, 8, 9)
YEAR = 2026
PERIOD_END = dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc)
PLANS = (Decimal("19.00"), Decimal("49.00"), Decimal("99.00"), Decimal("249.00"))
CURRENCIES = ("EUR",) * 6 + ("USD",) * 3 + ("GBP",)
USAGE_INVOICES = 40
ON_HOLD = 30
OPEN = 120
VOID = 50
MANUAL = 25
LATE_MANUAL = 8
LATE_ON_LAST_DAY = 2
NO_LATE_DAYS = (dt.date(2026, 7, 31), dt.date(2026, 8, 31), dt.date(2026, 9, 30))
BATCH = 500
BOUNDARY_LOSSES = (1, 1, 2, 1, 1, 1)
BLANK_ADDRESSES = 10
HELSINKI = ZoneInfo("Europe/Helsinki")
STATUS_CODES = {"P": "paid", "O": "open", "V": "void", "H": "on_hold"}
MIGRATED_CODES = ("P", "O", "V")
CENT = Decimal("0.01")

FIRST = ("Northwind", "Bluefield", "Copperleaf", "Lakeside", "Brightline", "Granite", "Silverpine", "Harbor",
         "Redwood", "Starling", "Juniper", "Meadow", "Ironbark", "Clearwater", "Foxglove", "Kestrel")
SECOND = ("Labs", "Studio", "Analytics", "Systems", "Works", "Partners", "Digital", "Logistics", "Health",
          "Media", "Robotics", "Foods", "Energy", "Travel", "Design", "Finance")
STREETS = ("Market Street", "Harbour Road", "Station Square", "Mill Lane", "Park Avenue", "Canal Street",
           "Orchard Way", "Bridge Road", "King Street", "Elm Grove")
COUNTRIES = ("DE", "FR", "NL", "SE", "FI", "GB", "US", "ES", "IT", "PL", "IE", "DK")

CUSTOMER_HEADER = ["customer_no", "name", "country", "address_line1", "address_line2", "created_at"]
TARGET_CUSTOMER_HEADER = ["customer_id", "name", "country", "address_line1", "address_line2", "created_at"]
INVOICE_HEADER = ["invoice_no", "customer_no", "issued_at", "amount", "currency", "status_code"]
TARGET_INVOICE_HEADER = ["invoice_no", "customer_id", "issued_at", "amount", "currency", "status"]
PAYMENT_HEADER = ["payment_id", "invoice_no", "paid_at", "amount", "channel"]
TARGET_PAYMENT_HEADER = ["payment_id", "invoice_no", "paid_at", "amount", "channel", "batch_no"]


@dataclass
class Customer:
    customer_no: str
    customer_id: str
    name: str
    country: str
    address_line1: str
    address_line2: str
    created_at: dt.datetime


@dataclass
class Invoice:
    invoice_no: str
    customer: Customer
    issued_at: dt.datetime
    amount: Decimal
    currency: str
    status_code: str = "P"


@dataclass
class Payment:
    payment_id: str
    invoice: Invoice
    paid_at: dt.datetime  # the true time, UTC
    channel: str
    migrated_at: dt.datetime | None = None  # paid_at as the move read it: manual local time taken for UTC
    batch_no: int | None = None


def utc(value: dt.datetime) -> str:
    return value.isoformat()


def local(value: dt.datetime) -> str:
    return value.astimezone(HELSINKI).replace(tzinfo=None).isoformat()


def truncate(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_DOWN)


def make_customers(rng: random.Random) -> list[Customer]:
    customers = []
    for n in range(CUSTOMERS):
        line2 = rng.choice(("", "", "", f"Suite {rng.randint(1, 40)}", f"Floor {rng.randint(1, 12)}"))
        created = dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=rng.randint(0, 110_000_000))
        customers.append(Customer(f"C{10001 + n}", "cus_" + token(rng), f"{rng.choice(FIRST)} {rng.choice(SECOND)}",
                                  rng.choice(COUNTRIES), f"{rng.randint(1, 240)} {rng.choice(STREETS)}", line2, created))
    return customers


def make_invoices(rng: random.Random, customers: list[Customer]) -> list[Invoice]:
    drafts = []
    for customer in customers:
        day, plan, currency = rng.randint(1, 28), rng.choice(PLANS), rng.choice(CURRENCIES)
        for month in MONTHS:
            issued = dt.datetime(YEAR, month, day, rng.randint(6, 18), rng.randint(0, 59), rng.randint(0, 59),
                                 tzinfo=dt.timezone.utc)
            drafts.append((issued, customer.customer_no, customer, plan, currency))
    drafts.sort(key=lambda d: (d[0], d[1]))
    invoices = [Invoice(f"INV-{YEAR}-{n + 1:05d}", c, issued, plan, currency)
                for n, (issued, _, c, plan, currency) in enumerate(drafts)]
    for invoice in rng.sample(invoices, USAGE_INVOICES):
        invoice.amount = Decimal(rng.randint(1_000, 99_999)) / 100 + Decimal(rng.randint(1, 99)) / 10_000
    others = rng.sample(invoices, ON_HOLD + OPEN + VOID)
    for invoice, code in zip(others, ["H"] * ON_HOLD + ["O"] * OPEN + ["V"] * VOID):
        invoice.status_code = code
    return invoices


def make_payments(rng: random.Random, invoices: list[Invoice]) -> list[Payment]:
    paid = [i for i in invoices if i.status_code == "P"]
    drafts = []
    for invoice in paid:
        room = min(dt.timedelta(days=12), PERIOD_END - dt.timedelta(seconds=1) - invoice.issued_at)
        delay = dt.timedelta(seconds=rng.randint(600, max(600, int(room.total_seconds()))))
        drafts.append((invoice.issued_at + delay, invoice))
    drafts.sort(key=lambda d: (d[0], d[1].invoice_no))
    payments = [Payment(f"P{100001 + n}", invoice, paid_at, "card" if rng.random() < 0.7 else "bank")
                for n, (paid_at, invoice) in enumerate(drafts)]
    set_manual_payments(rng, payments)
    return payments


def set_manual_payments(rng: random.Random, payments: list[Payment]) -> None:
    """25 manual payments: 8 paid between 21:00 and 23:59 UTC, so the +3 h of the move pushes them to the next
    day, 2 of those on 30 September (into October) and none on 31 July or 31 August; 17 paid earlier in the day.
    Only payments made a day or more after their invoice, so any time of that day stays after the invoice."""
    later = [p for p in payments if p.paid_at.date() > p.invoice.issued_at.date()]
    last_day = rng.sample([p for p in later if p.paid_at.date() == NO_LATE_DAYS[-1]], LATE_ON_LAST_DAY)
    other_late = rng.sample([p for p in later if p.paid_at.date() not in NO_LATE_DAYS], LATE_MANUAL - LATE_ON_LAST_DAY)
    chosen = set(map(id, last_day + other_late))
    early = rng.sample([p for p in later if id(p) not in chosen], MANUAL - LATE_MANUAL)
    for payment, hours in [(p, (21, 23)) for p in last_day + other_late] + [(p, (0, 20)) for p in early]:
        day = payment.paid_at.date()
        payment.paid_at = dt.datetime(day.year, day.month, day.day, rng.randint(*hours), rng.randint(0, 59),
                                      rng.randint(0, 59), tzinfo=dt.timezone.utc)
        payment.channel = "manual"


def migrate(payments: list[Payment]) -> list[Payment]:
    """The move as it ran: read paid_at (manual local time taken for UTC), then batches of 500 by paid_at, each
    batch selected with paid_at > the largest paid_at of the previous one. At the 6 batch boundaries a block of
    card and bank payments shares one time; the rows of a block that did not fit the batch are skipped forever.
    Returns the payments that reached the target."""
    for p in payments:
        p.migrated_at = local_as_utc(p.paid_at) if p.channel == "manual" else p.paid_at
    order = unique_times(sorted(payments, key=lambda p: (p.migrated_at, p.payment_id)))
    start = 0
    for lost in BOUNDARY_LOSSES:
        block = order[start + BATCH - 1: start + BATCH + lost]
        assert all(p.channel != "manual" for p in block), "a manual payment sits on a batch boundary"
        for p in block[1:]:
            p.paid_at = p.migrated_at = block[0].migrated_at
        start += BATCH + lost
    order.sort(key=lambda p: (p.migrated_at, p.payment_id))
    moved, last, batch_no = [], None, 0
    while True:
        batch = [p for p in order if last is None or p.migrated_at > last][:BATCH]
        if not batch:
            return moved
        batch_no += 1
        for p in batch:
            p.batch_no = batch_no
        moved += batch
        last = batch[-1].migrated_at


def local_as_utc(value: dt.datetime) -> dt.datetime:
    return value.astimezone(HELSINKI).replace(tzinfo=dt.timezone.utc)


def unique_times(order: list[Payment]) -> list[Payment]:
    """Move any payment that shares a second with an earlier one a second later, so only the planted blocks tie."""
    for before, after in zip(order, order[1:]):
        if after.migrated_at <= before.migrated_at:
            after.migrated_at = before.migrated_at + dt.timedelta(seconds=1)
            if after.channel != "manual":
                after.paid_at = after.migrated_at
            else:
                after.paid_at = after.migrated_at - (local_as_utc(after.paid_at) - after.paid_at)
    return order


def generate(out: Path) -> None:
    rng = random.Random(SEED)
    customers = make_customers(rng)
    for customer in rng.sample([c for c in customers if not c.address_line2], BLANK_ADDRESSES):
        customer.address_line2 = " "
    invoices = make_invoices(rng, customers)
    payments = make_payments(rng, invoices)
    moved = migrate(payments)
    moved_ids = {p.payment_id for p in moved}

    truth = [LoadTruth(DATASET, "customers", "whitespace_to_null", c.customer_no, "address_line2", None)
             for c in customers if c.address_line2 == " "]
    truth += [LoadTruth(DATASET, "invoices", "truncated_decimal", i.invoice_no, "amount", truncate(i.amount) - i.amount)
              for i in invoices if truncate(i.amount) != i.amount]
    truth += [LoadTruth(DATASET, "invoices", "schema_drift", i.invoice_no, "status", None)
              for i in invoices if i.status_code not in MIGRATED_CODES]
    truth += [LoadTruth(DATASET, "payments", "timezone_shift", p.payment_id, "paid_at", Decimal(3))
              for p in payments if p.channel == "manual"]
    truth += [LoadTruth(DATASET, "payments", "batch_boundary_loss", p.payment_id, None, Decimal(-1))
              for p in payments if p.payment_id not in moved_ids]

    write_csv(out / "legacy_customers.csv", CUSTOMER_HEADER, [
        [c.customer_no, c.name, c.country, c.address_line1, c.address_line2, utc(c.created_at)] for c in customers])
    write_csv(out / "legacy_invoices.csv", INVOICE_HEADER, [
        [i.invoice_no, i.customer.customer_no, utc(i.issued_at), f"{i.amount:.4f}", i.currency, i.status_code]
        for i in invoices])
    write_csv(out / "legacy_payments.csv", PAYMENT_HEADER, [
        [p.payment_id, p.invoice.invoice_no, local(p.paid_at) if p.channel == "manual" else utc(p.paid_at),
         f"{money(p.invoice.amount):.2f}", p.channel] for p in payments])
    write_csv(out / "target_customers.csv", TARGET_CUSTOMER_HEADER, [
        [c.customer_id, c.name, c.country, c.address_line1, c.address_line2.strip(), utc(c.created_at)]
        for c in customers])
    write_csv(out / "target_invoices.csv", TARGET_INVOICE_HEADER, [
        [i.invoice_no, i.customer.customer_id, utc(i.issued_at), f"{truncate(i.amount):.2f}", i.currency,
         STATUS_CODES[i.status_code] if i.status_code in MIGRATED_CODES else ""] for i in invoices])
    write_csv(out / "target_payments.csv", TARGET_PAYMENT_HEADER, [
        [p.payment_id, p.invoice.invoice_no, utc(p.migrated_at), f"{money(p.invoice.amount):.2f}", p.channel,
         p.batch_no] for p in moved])
    write_csv(out / "status_map.csv", ["legacy_code", "status"], [[c, STATUS_CODES[c]] for c in MIGRATED_CODES])
    write_csv(out / "key_map.csv", ["customer_no", "customer_id"], [[c.customer_no, c.customer_id] for c in customers])
    write_csv(out / "truth.csv", LOAD_TRUTH_HEADER, load_truth_rows(truth))
