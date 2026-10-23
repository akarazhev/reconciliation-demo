import csv
import datetime as dt
import hashlib
from collections import Counter

from generator import opt_torg, subscribe_co

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


def test_opt_torg_is_deterministic(tmp_path):
    opt_torg.generate(tmp_path / "a")
    opt_torg.generate(tmp_path / "b")
    assert digest(tmp_path / "a") == digest(tmp_path / "b")


def test_opt_torg_planted_counts(tmp_path):
    opt_torg.generate(tmp_path)
    truth = read(tmp_path / "truth.csv")
    assert Counter(r["cause"] for r in truth) == {
        "deleted_left_behind": 12, "changed_not_exported": 45, "late_item_not_updated": 8,
        "payment_wrong_invoice": 6, "duplicate_after_rerun": 20,
    }
    assert len(truth) == 91


def test_opt_torg_row_counts(tmp_path):
    opt_torg.generate(tmp_path)
    counts = {name: len(read(tmp_path / f"{name}.csv")) for name in (
        "source_invoices", "source_lines", "source_payments", "source_article_renames",
        "target_invoices", "target_lines", "target_payments", "export_runs")}
    assert counts == {
        "source_invoices": 900, "source_lines": 3600, "source_payments": 850, "source_article_renames": 8,
        "target_invoices": 1200, "target_lines": 3632, "target_payments": 850, "export_runs": 31,
    }


def test_opt_torg_constraints(tmp_path):
    opt_torg.generate(tmp_path)
    source_docs = {r["doc_guid"]: r for r in read(tmp_path / "source_invoices.csv")}
    target_docs = {r["doc_guid"]: r for r in read(tmp_path / "target_invoices.csv")}
    changed = {g for g, r in source_docs.items() if r["total"] != target_docs[g]["total"]}
    assert len(changed) == 15
    source_lines = {r["line_guid"] for r in read(tmp_path / "source_lines.csv")}
    target_lines = read(tmp_path / "target_lines.csv")
    deleted = [r for r in target_lines if r["line_guid"] not in source_lines]
    assert len(deleted) == 12 and {r["doc_guid"] for r in deleted} <= changed
    renames = read(tmp_path / "source_article_renames.csv")
    for rename in renames:
        uses = [r for r in target_lines if r["article"] == rename["old_article"]]
        assert len(uses) == 1 and uses[0]["doc_guid"] not in changed, rename["old_article"]
    runs = read(tmp_path / "export_runs.csv")
    assert sorted(r["run"] for r in runs if r["export_night"] == "2026-09-17") == ["1", "2"]
    assert sum(r["export_run"] == "2" for r in target_lines) == 20
    assert {r["export_night"] for r in target_lines if r["export_run"] == "2"} == {"2026-09-17"}
    old_numbers = {r["number"] for g, r in target_docs.items() if g not in source_docs}
    assert len(old_numbers) == 300
    paid = {r["invoice_guid"] for r in read(tmp_path / "source_payments.csv")}
    assert sum(r["number"] in old_numbers for g, r in source_docs.items() if g in paid) == 6
    assert sum(r["number"] in old_numbers for g, r in source_docs.items() if g not in paid) == 0


def valid_inn(inn):
    weights = (2, 4, 10, 3, 5, 9, 4, 6, 8)
    return len(inn) == 10 and sum(w * int(d) for w, d in zip(weights, inn)) % 11 % 10 == int(inn[9])


def test_opt_torg_inns_are_made_up(tmp_path):
    opt_torg.generate(tmp_path)
    inns = {r["customer_inn"] for name in ("source_invoices", "target_invoices") for r in read(tmp_path / f"{name}.csv")}
    assert inns and not [inn for inn in inns if valid_inn(inn)]
