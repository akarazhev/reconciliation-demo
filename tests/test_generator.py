import csv
import datetime as dt
import hashlib
from collections import Counter, defaultdict
from decimal import Decimal

from generator import eu_shop


def read(path, delimiter=","):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def digest(folder):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}


def test_eu_shop_is_byte_identical_for_the_same_seed(tmp_path):
    eu_shop.generate(tmp_path / "a")
    eu_shop.generate(tmp_path / "b")
    assert digest(tmp_path / "a") == digest(tmp_path / "b")


def test_eu_shop_plants_the_18_discrepancies_of_the_spec(tmp_path):
    eu_shop.generate(tmp_path)
    truth = read(tmp_path / "truth.csv")
    assert Counter(r["cause"] for r in truth) == {
        "duplicate": 3, "missing_in_ledger": 3, "in_transit": 1, "partial": 2,
        "fee": 3, "fx": 2, "amount_mismatch": 2, "unbooked": 2,
    }
    assert len({(r["key"], r["kind"]) for r in truth}) == 18
    assert Decimal("-63.00") in {Decimal(r["difference"]) for r in truth if r["cause"] == "amount_mismatch"}


def test_eu_shop_payouts_equal_their_items_and_only_the_last_arrives_in_october(tmp_path):
    eu_shop.generate(tmp_path)
    items = read(tmp_path / "stripe_balance.csv")
    payouts = read(tmp_path / "stripe_payouts.csv")
    sums = defaultdict(Decimal)
    for r in items:
        assert r["automatic_payout_id"], r["balance_transaction_id"]
        assert r["created_utc"].startswith("2026-09-")
        sums[r["automatic_payout_id"]] += Decimal(r["net"])
    assert {p["id"]: Decimal(p["amount"]) / 100 for p in payouts} == dict(sums)
    arrivals = [dt.datetime.fromtimestamp(int(p["arrival_date"]), dt.UTC).date() for p in payouts]
    assert len(payouts) == 22
    assert sum(a > dt.date(2026, 9, 30) for a in arrivals) == 1


def test_eu_shop_bank_has_every_arrived_payout_and_other_rows(tmp_path):
    eu_shop.generate(tmp_path)
    bank = read(tmp_path / "bank.csv")
    payout_ids = {p["id"] for p in read(tmp_path / "stripe_payouts.csv")}
    referenced = {r["reference"].removeprefix("STRIPE PAYOUT ") for r in bank if r["counterparty"] == "STRIPE"}
    assert referenced == payout_ids
    assert any(r["counterparty"] != "STRIPE" for r in bank)
from generator import ozon_seller


def test_ozon_is_byte_identical_for_the_same_seed(tmp_path):
    ozon_seller.generate(tmp_path / "a")
    ozon_seller.generate(tmp_path / "b")
    assert digest(tmp_path / "a") == digest(tmp_path / "b")


def test_ozon_plants_the_17_discrepancies_of_the_spec(tmp_path):
    ozon_seller.generate(tmp_path)
    truth = read(tmp_path / "truth.csv")
    assert Counter(r["cause"] for r in truth) == {
        "duplicate": 2, "missing_in_ledger": 3, "in_transit": 1, "partial": 3, "fee": 3, "unbooked": 5,
    }
    assert len({(r["key"], r["kind"]) for r in truth}) == 17


def test_ozon_payouts_equal_their_period_and_the_second_lands_in_october(tmp_path):
    ozon_seller.generate(tmp_path)
    lines = read(tmp_path / "ozon_report.csv", delimiter=";")
    payouts = read(tmp_path / "ozon_payouts.csv", delimiter=";")

    def day(text):
        return dt.datetime.strptime(text, "%d.%m.%Y").date()

    def amount(text):
        return Decimal(text.replace(",", "."))

    assert [p["Дата выплаты"] for p in payouts] == ["16.09.2026", "01.10.2026"]
    for p in payouts:
        start, end = day(p["Период с"]), day(p["Период по"])
        in_period = [amount(r["Сумма итого, руб."]) for r in lines if start <= day(r["Дата начисления"]) <= end]
        assert sum(in_period, Decimal("0")) == amount(p["Сумма, руб."])
    assert all(dt.date(2026, 9, 1) <= day(r["Дата начисления"]) <= dt.date(2026, 9, 30) for r in lines)
    two_unit = Counter((r["Номер отправления"], r["Тип начисления"]) for r in lines if r["Тип начисления"] == "Продажа")
    assert max(two_unit.values()) == 2


from generator import wb_seller


def wb_line_total(row):
    """Money of one report row as the books see it: a sale is retail minus commission, so ppvz_for_pay;
    a return withholds ppvz_for_pay; services are charged at their own column."""
    d = {k: Decimal(row[k]) for k in ("ppvz_for_pay", "delivery_rub", "storage_fee", "penalty", "deduction")}
    sign = {"Продажа": 1, "Возврат": -1}.get(row["supplier_oper_name"], 0)
    return sign * d["ppvz_for_pay"] - d["delivery_rub"] - d["storage_fee"] - d["penalty"] - d["deduction"]


def test_wb_is_byte_identical_for_the_same_seed(tmp_path):
    wb_seller.generate(tmp_path / "a")
    wb_seller.generate(tmp_path / "b")
    assert digest(tmp_path / "a") == digest(tmp_path / "b")


def test_wb_plants_the_15_discrepancies_of_the_design(tmp_path):
    wb_seller.generate(tmp_path)
    truth = read(tmp_path / "truth.csv")
    assert Counter(r["cause"] for r in truth) == {
        "duplicate": 2, "missing_in_ledger": 2, "partial": 2, "fee": 3, "unbooked": 5, "in_transit": 1,
    }
    assert len({(r["key"], r["kind"]) for r in truth}) == 15


def test_wb_reports_are_cut_to_september_and_the_last_is_paid_in_october(tmp_path):
    wb_seller.generate(tmp_path)
    reports = read(tmp_path / "wb_reports.csv")
    assert [(r["date_from"], r["date_to"]) for r in reports] == [
        ("2026-09-01", "2026-09-06"), ("2026-09-07", "2026-09-13"), ("2026-09-14", "2026-09-20"),
        ("2026-09-21", "2026-09-27"), ("2026-09-28", "2026-09-30"),
    ]
    assert [r["payment_date"] for r in reports][-1] == "2026-10-02"
    assert all(r["payment_date"] <= "2026-09-30" for r in reports[:-1])


def test_wb_report_totals_equal_their_rows_without_a_second_commission(tmp_path):
    wb_seller.generate(tmp_path)
    rows = read(tmp_path / "wb_report.csv")
    reports = {r["realizationreport_id"]: r for r in read(tmp_path / "wb_reports.csv")}
    totals = defaultdict(Decimal)
    for row in rows:
        report = reports[row["realizationreport_id"]]
        assert report["date_from"] <= row["rr_dt"] <= report["date_to"]
        if row["supplier_oper_name"] == "Продажа":
            assert Decimal(row["ppvz_for_pay"]) < Decimal(row["retail_price_withdisc_rub"])
        totals[row["realizationreport_id"]] += wb_line_total(row)
    assert {k: Decimal(r["total_payable"]) for k, r in reports.items()} == dict(totals)


def test_wb_bank_names_every_report_in_its_reference(tmp_path):
    wb_seller.generate(tmp_path)
    bank = [r for r in read(tmp_path / "bank.csv") if r["counterparty"] == "WILDBERRIES"]
    reports = read(tmp_path / "wb_reports.csv")
    assert [(r["booking_date"], r["amount"]) for r in bank] == [(r["payment_date"], r["total_payable"]) for r in reports]
    assert all(r["realizationreport_id"] in b["reference"].split() for r, b in zip(reports, bank, strict=True))
