import csv
import datetime as dt
import hashlib
from collections import Counter

from generator import subscribe_co

HELSINKI_SUMMER = dt.timedelta(hours=3)


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def digest(folder):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}


def test_subscribe_co_is_deterministic(tmp_path):
    subscribe_co.generate(tmp_path / "a")
    subscribe_co.generate(tmp_path / "b")
    assert digest(tmp_path / "a") == digest(tmp_path / "b")


def test_subscribe_co_planted_counts(tmp_path):
    subscribe_co.generate(tmp_path)
    truth = read(tmp_path / "truth.csv")
    assert Counter(r["cause"] for r in truth) == {
        "truncated_decimal": 40, "timezone_shift": 25, "batch_boundary_loss": 7,
        "schema_drift": 30, "whitespace_to_null": 10,
    }
    assert len(truth) == 112


def test_subscribe_co_row_counts(tmp_path):
    subscribe_co.generate(tmp_path)
    counts = {name: len(read(tmp_path / f"{name}.csv")) for name in (
        "legacy_customers", "legacy_invoices", "legacy_payments",
        "target_customers", "target_invoices", "target_payments", "key_map")}
    assert counts == {
        "legacy_customers": 1200, "legacy_invoices": 3600, "legacy_payments": 3400,
        "target_customers": 1200, "target_invoices": 3600, "target_payments": 3393, "key_map": 1200,
    }
    assert sorted(r["legacy_code"] for r in read(tmp_path / "status_map.csv")) == ["O", "P", "V"]


def test_subscribe_co_constraints(tmp_path):
    subscribe_co.generate(tmp_path)
    legacy = read(tmp_path / "legacy_payments.csv")
    target_ids = {r["payment_id"] for r in read(tmp_path / "target_payments.csv")}
    manual = [r for r in legacy if r["channel"] == "manual"]
    assert len(manual) == 25
    true_utc = [dt.datetime.fromisoformat(r["paid_at"]) - HELSINKI_SUMMER for r in manual]
    late = [t for t in true_utc if t.hour >= 21]
    assert len(late) == 8
    assert sum(t.date() == dt.date(2026, 9, 30) for t in late) == 2
    assert not any(t.date() in (dt.date(2026, 7, 31), dt.date(2026, 8, 31)) for t in late)
    lost = [r for r in legacy if r["payment_id"] not in target_ids]
    assert len(lost) == 7
    assert {r["channel"] for r in lost} <= {"card", "bank"}
    assert {int(r["batch_no"]) for r in read(tmp_path / "target_payments.csv")} == set(range(1, 8))


def test_single_space_survives_csv(tmp_path):
    subscribe_co.generate(tmp_path)
    customers = read(tmp_path / "legacy_customers.csv")
    assert sum(r["address_line2"] == " " for r in customers) == 10
