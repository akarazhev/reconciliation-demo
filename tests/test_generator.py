import csv
import datetime as dt
import hashlib
from collections import Counter, defaultdict
from decimal import Decimal

from generator import eu_shop, eu_shop_october


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
def test_october_is_byte_identical_for_the_same_seed(tmp_path):
    eu_shop_october.generate(tmp_path / "a")
    eu_shop_october.generate(tmp_path / "b")
    assert digest(tmp_path / "a") == digest(tmp_path / "b")


def test_october_starts_with_eu_shop_september_row_for_row(tmp_path):
    eu_shop.generate(tmp_path / "sep")
    eu_shop_october.generate(tmp_path / "oct")
    end = dt.datetime(2026, 9, 30, 23, 59, 59, tzinfo=dt.UTC).timestamp()

    def september(name, column):
        return [r for r in read(tmp_path / "oct" / name) if r[column] <= "2026-09-30 23:59:59"]

    assert september("stripe_balance.csv", "created_utc") == read(tmp_path / "sep" / "stripe_balance.csv")
    assert september("ledger.csv", "date") == read(tmp_path / "sep" / "ledger.csv")
    assert september("bank.csv", "booking_date") == [r for r in read(tmp_path / "sep" / "bank.csv")
                                                     if r["booking_date"] <= "2026-09-30"]
    assert [p for p in read(tmp_path / "oct" / "stripe_payouts.csv") if int(p["created"]) <= end] \
        == read(tmp_path / "sep" / "stripe_payouts.csv")


def test_october_plants_only_the_month_end_cases(tmp_path):
    eu_shop.generate(tmp_path / "sep")
    eu_shop_october.generate(tmp_path / "oct")
    september = read(tmp_path / "sep" / "truth.csv")
    october = read(tmp_path / "oct" / "truth.csv")
    assert Counter((r["level"], r["cause"], r["kind"]) for r in october) == {
        ("operation", "fx", "refund"): 1, ("operation", "unbooked", "charge"): 1, ("bank", "in_transit", "payout"): 3}
    won = next(r for r in october if r["cause"] == "unbooked")
    lost = next(r for r in september if r["key"] == won["key"])
    assert Decimal(lost["difference"]) + Decimal(won["difference"]) == -eu_shop.DISPUTE_FEE
    arrived = next(r for r in september if r["cause"] == "in_transit")
    transit = {r["key"]: Decimal(r["difference"]) for r in october if r["cause"] == "in_transit"}
    assert transit.pop(arrived["key"]) == -Decimal(arrived["difference"]) > 0
    assert len(transit) == 2 and all(v < 0 for v in transit.values())
    refund = next(r for r in october if r["cause"] == "fx")
    charge = next(r for r in read(tmp_path / "oct" / "stripe_balance.csv")
                  if r["payment_metadata[order_id]"] == refund["key"] and r["reporting_category"] == "charge")
    assert charge["created_utc"].startswith("2026-09-") and charge["customer_facing_currency"] == "usd"
    assert refund["key"] not in {r["key"] for r in september}
    assert Decimal("0") < Decimal(refund["difference"]) < Decimal(charge["gross"]) / 50


def test_october_payouts_equal_their_items_and_two_arrive_in_november(tmp_path):
    eu_shop_october.generate(tmp_path)
    items = read(tmp_path / "stripe_balance.csv")
    payouts = read(tmp_path / "stripe_payouts.csv")
    sums = defaultdict(Decimal)
    for r in items:
        assert r["automatic_payout_id"], r["balance_transaction_id"]
        sums[r["automatic_payout_id"]] += Decimal(r["net"])
    assert {p["id"]: Decimal(p["amount"]) / 100 for p in payouts} == dict(sums)
    october = [p for p in payouts
               if dt.datetime.fromtimestamp(int(p["created"]), dt.UTC).date() >= dt.date(2026, 10, 1)]
    arrivals = sorted(dt.datetime.fromtimestamp(int(p["arrival_date"]), dt.UTC).date() for p in october)
    assert len(october) == 23
    assert arrivals[-2:] == [dt.date(2026, 11, 2), dt.date(2026, 11, 3)]
    saturday = {r["automatic_payout_id"] for r in items if r["created_utc"].startswith("2026-10-31")}
    assert len(saturday) == 1
    assert {r["reporting_category"] for r in items if r["created_utc"].startswith("2026-10-")} == {
        "charge", "refund", "dispute_reversal"}


def test_october_bank_has_every_arrived_payout(tmp_path):
    eu_shop_october.generate(tmp_path)
    bank = read(tmp_path / "bank.csv")
    referenced = {r["reference"].removeprefix("STRIPE PAYOUT ") for r in bank if r["counterparty"] == "STRIPE"}
    assert referenced == {p["id"] for p in read(tmp_path / "stripe_payouts.csv")}
    assert max(r["booking_date"] for r in bank) <= "2026-11-07"


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


def test_wb_unit_tests_feed_the_real_mapping():
    from pathlib import Path

    import yaml

    root = Path(__file__).resolve().parents[1]
    with (root / "dbt" / "seeds" / "kind_map_wb.csv").open(encoding="utf-8", newline="") as f:
        seed = sorted(tuple(r.values()) for r in csv.DictReader(f))
    spec = yaml.safe_load((root / "dbt" / "models" / "staging" / "wb" / "_wb.yml").read_text(encoding="utf-8"))
    for test in spec["unit_tests"]:
        given = next(g for g in test["given"] if g["input"] == "ref('kind_map_wb')")
        rows = sorted((r["supplier_oper_name"], r["part"], r["kind"], str(r["sign"]), r["code"]) for r in given["rows"])
        assert rows == seed, test["name"]
