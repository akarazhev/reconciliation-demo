"""A made-up wholesale company exports invoices, their lines and payments for September 2026 from 1C to MySQL
every night: each night picks the documents dated the previous day. Invoices and payments are upserted by GUID,
the lines table has no unique key, and deletions are not exported. Invoice numbers in 1C restart every year,
and MySQL also holds 300 invoices of September 2025 from earlier exports; the export links a payment to the
earliest invoice with the number the payment names.

Writes the 1C side (source_*.csv, source_article_renames.csv), the MySQL side (target_*.csv), export_runs.csv and
truth.csv: the export as it ran, then what happened in 1C afterwards, every difference recorded in truth.csv.
"""
import datetime as dt
import random
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from generator.common import token, write_csv
from generator.load_common import LOAD_TRUTH_HEADER, LoadTruth, load_truth_rows

SEED = 20260902
DATASET = "opt_torg"
FIRST_DAY = dt.date(2026, 9, 1)
DAYS = 30
INVOICES_PER_DAY = 30
LINES = 3600
UNPAID = 50
OLD_INVOICES = 300
FIRST_NUMBER = 6101
FIRST_OLD_NUMBER = 5807  # last September's numbers run up to 6106, so 6101-6106 exist in both years
CHANGED = 15
DELETED = 12
RENAMED = 8
RERUN_NIGHT = dt.date(2026, 9, 17)
RERUN_LINES = 20
MOSCOW = dt.timezone(dt.timedelta(hours=3))
NIGHT_START = dt.time(2, 0)
RERUN_START = dt.time(4, 30)

INVOICE_HEADER = ["doc_guid", "number", "doc_date", "customer_inn", "total", "modified_at"]
LINE_HEADER = ["line_guid", "doc_guid", "line_no", "article", "qty", "price", "amount"]
PAYMENT_HEADER = ["payment_guid", "invoice_guid", "number", "pay_date", "amount"]
EXPORT = ["export_night", "export_run"]


@dataclass
class Line:
    line_guid: str
    line_no: int
    article: str
    qty: int
    price: Decimal

    @property
    def amount(self) -> Decimal:
        return self.qty * self.price


@dataclass
class Invoice:
    doc_guid: str
    number: str
    doc_date: dt.date
    customer_inn: str
    modified_at: dt.datetime
    lines: list[Line] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum((line.amount for line in self.lines), Decimal("0.00"))

    @property
    def night(self) -> dt.date:
        return self.doc_date + dt.timedelta(days=1)


def guid(rng: random.Random) -> str:
    return "-".join(token(rng, n).lower() for n in (8, 4, 4, 4, 12))


def inn(rng: random.Random) -> str:
    """A ten-digit INN whose check digit is wrong on purpose, so it cannot be a real organisation's."""
    digits = "7" + "".join(str(rng.randint(0, 9)) for _ in range(9))
    check = sum(w * int(d) for w, d in zip((2, 4, 10, 3, 5, 9, 4, 6, 8), digits)) % 11 % 10
    return digits[:9] + str((check + 1) % 10)


def make_invoices(rng: random.Random) -> list[Invoice]:
    customers = [inn(rng) for _ in range(120)]
    invoices = []
    for day in range(DAYS):
        doc_date = FIRST_DAY + dt.timedelta(days=day)
        for _ in range(INVOICES_PER_DAY):
            modified = dt.datetime.combine(doc_date, dt.time(rng.randint(9, 18), rng.randint(0, 59)), MOSCOW)
            invoices.append(Invoice(guid(rng), f"{FIRST_NUMBER + len(invoices):08d}", doc_date,
                                    rng.choice(customers), modified))
    exported_lines = LINES + DELETED  # the lines 1C holds after the deletions, plus the deleted ones
    counts = [rng.randint(2, 6) for _ in invoices]
    while sum(counts) != exported_lines:
        n = rng.randrange(len(counts))
        if sum(counts) > exported_lines and counts[n] > 2:
            counts[n] -= 1
        elif sum(counts) < exported_lines and counts[n] < 6:
            counts[n] += 1
    articles = [f"A-{10001 + n}" for n in range(400)]
    for invoice, count in zip(invoices, counts):
        invoice.lines = [Line(guid(rng), n + 1, rng.choice(articles), rng.randint(1, 40),
                              Decimal(rng.randint(5_000, 500_000)) / 100) for n in range(count)]
    return invoices


def old_invoices(rng: random.Random) -> list[list]:
    """Last September's invoices, exported long ago: in MySQL only."""
    rows = []
    for n in range(OLD_INVOICES):
        doc_date = dt.date(2025, 9, 1) + dt.timedelta(days=n // 10)
        rows.append([guid(rng), f"{FIRST_OLD_NUMBER + n:08d}", doc_date.isoformat(), inn(rng),
                     f"{Decimal(rng.randint(10_000, 9_000_000)) / 100:.2f}", (doc_date + dt.timedelta(days=1)).isoformat(), 1])
    return rows


def generate(out: Path) -> None:
    rng = random.Random(SEED)
    invoices = make_invoices(rng)
    old = old_invoices(rng)
    old_numbers = {row[1] for row in old}
    overlap = [i for i in invoices if i.number in old_numbers]
    rerun_docs = [i for i in invoices if i.night == RERUN_NIGHT]
    others = [i for i in invoices if i not in overlap and i not in rerun_docs]
    picked = rng.sample(others, CHANGED + RENAMED + UNPAID)
    changed, renamed_docs, unpaid = picked[:CHANGED], picked[CHANGED:CHANGED + RENAMED], picked[CHANGED + RENAMED:]

    # The export, night by night: every invoice and line as it stood when its night ran.
    exported = {i.doc_guid: (i.total, [Line(x.line_guid, x.line_no, x.article, x.qty, x.price) for x in i.lines])
                for i in invoices}
    rerun_lines = [line for i in rerun_docs for line in exported[i.doc_guid][1]][:RERUN_LINES]
    used = {line.article for i in invoices for line in i.lines}
    renames = []
    for n, invoice in enumerate(renamed_docs):
        old_code, new_code = f"A-9{1001 + n:04d}", f"A-9{2001 + n:04d}"
        assert old_code not in used and new_code not in used
        line = rng.choice(exported[invoice.doc_guid][1])
        line.article = old_code
        next(x for x in invoice.lines if x.line_guid == line.line_guid).article = new_code
        renamed_at = dt.datetime.combine(invoice.night, dt.time(rng.randint(9, 18), rng.randint(0, 59)), MOSCOW)
        renames.append([old_code, new_code, renamed_at.isoformat()])

    # After the export, in 1C: one quantity changed in each of 15 documents, and a line deleted in 12 of them.
    truth = []
    for n, invoice in enumerate(changed):
        candidates = [x for x in invoice.lines]
        line = rng.choice(candidates)
        old_qty = line.qty
        line.qty = old_qty + rng.choice((-1, 1)) * rng.randint(1, min(5, old_qty - 1) if old_qty > 1 else 1)
        if line.qty <= 0:
            line.qty = old_qty + 3
        if n < DELETED:
            gone = rng.choice([x for x in invoice.lines if x is not line])
            invoice.lines.remove(gone)
            truth.append(LoadTruth(DATASET, "lines", "deleted_left_behind", gone.line_guid, None, Decimal(1)))
        invoice.modified_at = dt.datetime.combine(invoice.night, dt.time(rng.randint(9, 18), rng.randint(0, 59)), MOSCOW)
        truth.append(LoadTruth(DATASET, "lines", "changed_not_exported", line.line_guid, "qty", Decimal(old_qty - line.qty)))
        truth.append(LoadTruth(DATASET, "lines", "changed_not_exported", line.line_guid, "amount",
                               (old_qty - line.qty) * line.price))
        truth.append(LoadTruth(DATASET, "invoices", "changed_not_exported", invoice.doc_guid, "total",
                               exported[invoice.doc_guid][0] - invoice.total))
    for invoice, (old_code, _, _) in zip(renamed_docs, renames):
        line = next(x for x in exported[invoice.doc_guid][1] if x.article == old_code)
        truth.append(LoadTruth(DATASET, "lines", "late_item_not_updated", line.line_guid, "article", None))
    truth += [LoadTruth(DATASET, "lines", "duplicate_after_rerun", line.line_guid, None, Decimal(1)) for line in rerun_lines]

    # Payments: one per paid invoice, linked at export by number to the earliest invoice with that number.
    paid = [i for i in invoices if i not in unpaid]
    earliest = {row[1]: row[0] for row in old}
    payments = []
    for invoice in paid:
        pay_date = min(invoice.doc_date + dt.timedelta(days=rng.randint(0, 9)), FIRST_DAY + dt.timedelta(days=DAYS - 1))
        linked = earliest.get(invoice.number, invoice.doc_guid)
        payments.append([guid(rng), invoice.doc_guid, linked, invoice.number, pay_date, exported[invoice.doc_guid][0]])
        if linked != invoice.doc_guid:
            truth.append(LoadTruth(DATASET, "payments", "payment_wrong_invoice", payments[-1][0], "invoice_guid", None))

    nights = [FIRST_DAY + dt.timedelta(days=d + 1) for d in range(DAYS)]
    runs = [[night.isoformat(), 1, dt.datetime.combine(night, NIGHT_START, MOSCOW).isoformat()] for night in nights]
    runs.insert(nights.index(RERUN_NIGHT) + 1,
                [RERUN_NIGHT.isoformat(), 2, dt.datetime.combine(RERUN_NIGHT, RERUN_START, MOSCOW).isoformat()])

    write_csv(out / "source_invoices.csv", INVOICE_HEADER, [
        [i.doc_guid, i.number, i.doc_date.isoformat(), i.customer_inn, f"{i.total:.2f}", i.modified_at.isoformat()]
        for i in invoices])
    write_csv(out / "source_lines.csv", LINE_HEADER, [
        [x.line_guid, i.doc_guid, x.line_no, x.article, x.qty, f"{x.price:.2f}", f"{x.amount:.2f}"]
        for i in invoices for x in i.lines])
    write_csv(out / "source_payments.csv", PAYMENT_HEADER, [
        [guid_, doc, number, pay_date.isoformat(), f"{amount:.2f}"] for guid_, doc, _, number, pay_date, amount in payments])
    write_csv(out / "source_article_renames.csv", ["old_article", "new_article", "renamed_at"], renames)
    write_csv(out / "target_invoices.csv", INVOICE_HEADER[:5] + EXPORT, old + [
        [i.doc_guid, i.number, i.doc_date.isoformat(), i.customer_inn, f"{exported[i.doc_guid][0]:.2f}",
         i.night.isoformat(), 1] for i in invoices])
    write_csv(out / "target_lines.csv", LINE_HEADER + EXPORT, [
        [x.line_guid, i.doc_guid, x.line_no, x.article, x.qty, f"{x.price:.2f}", f"{x.amount:.2f}", i.night.isoformat(), 1]
        for i in invoices for x in exported[i.doc_guid][1]] + [
        [x.line_guid, i.doc_guid, x.line_no, x.article, x.qty, f"{x.price:.2f}", f"{x.amount:.2f}", RERUN_NIGHT.isoformat(), 2]
        for i in rerun_docs for x in exported[i.doc_guid][1] if x in rerun_lines])
    write_csv(out / "target_payments.csv", PAYMENT_HEADER + EXPORT, [
        [guid_, linked, number, pay_date.isoformat(), f"{amount:.2f}", (pay_date + dt.timedelta(days=1)).isoformat(), 1]
        for guid_, _, linked, number, pay_date, amount in payments])
    write_csv(out / "export_runs.csv", ["export_night", "run", "started_at"], runs)
    write_csv(out / "truth.csv", LOAD_TRUTH_HEADER, load_truth_rows(truth))
