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
