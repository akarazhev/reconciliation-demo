"""End-to-end checks of the load check over the databases ./run.sh leaves behind; skipped before the first run."""
import csv
import json
import os
import shutil
import subprocess
from collections import Counter
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
FOUND = "select dataset, entity, cause, key, column_name, difference from main.load_discrepancies"


def load_datasets():
    with (ROOT / "dbt" / "seeds" / "load" / "load_datasets.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def rows(db, sql):
    if not db.exists():
        pytest.skip("run ./run.sh first")
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def planted(dataset):
    with (ROOT / "data" / dataset / "truth.csv").open(encoding="utf-8", newline="") as f:
        return [(r["dataset"], r["entity"], r["cause"], r["key"], r["column_name"] or None,
                 Decimal(r["difference"]) if r["difference"] else None) for r in csv.DictReader(f)]


def dbt(tmp_path, tz, *args):
    env = {**os.environ, "RECON_ROOT": str(tmp_path), "TZ": tz, "DBT_SEND_ANONYMOUS_USAGE_STATS": "false"}
    return subprocess.run(
        ["dbt", *args, "--project-dir", str(ROOT / "dbt"), "--profiles-dir", str(ROOT / "dbt"),
         "--target-path", str(tmp_path / "target"), "--log-path", str(tmp_path / "logs")],
        env=env, capture_output=True, text=True, timeout=300)


@pytest.mark.parametrize("dataset", [d["dataset"] for d in load_datasets()])
def test_load_found_exactly_what_was_planted(dataset):
    found = rows(ROOT / "data" / dataset / "recon.duckdb", FOUND)
    assert Counter(found) == Counter(planted(dataset))


def test_load_result_does_not_depend_on_session_time_zone(tmp_path):
    dataset = next(d for d in load_datasets() if d["dataset"] == "subscribe_co")
    shutil.copytree(ROOT / "data" / "subscribe_co", tmp_path / "data" / "subscribe_co",
                    ignore=shutil.ignore_patterns("recon.duckdb*"))
    relations = ", ".join(dataset["relations"].split(";"))
    result = dbt(tmp_path, "Asia/Tokyo", "build", "--select", "tag:load_check",
                 "--vars", f"{{dataset: subscribe_co, suite: load, load_relations: [{relations}]}}")
    assert result.returncode == 0, result.stdout + result.stderr
    everything = "select * from main.load_discrepancies order by entity, cause, key, column_name nulls first"
    in_tokyo = rows(tmp_path / "data" / "subscribe_co" / "recon.duckdb", everything)
    assert in_tokyo
    assert in_tokyo == rows(ROOT / "data" / "subscribe_co" / "recon.duckdb", everything)


def test_blank_means_only_whitespace(tmp_path):
    (tmp_path / "data" / "eu_shop").mkdir(parents=True)
    values = {"one_space": "' '", "two_spaces": "'  '", "tab": "chr(9)", "text": "' x '", "empty": "''"}
    sql = "select " + ", ".join(f'{{{{ load_is_blank("{v}") }}}} as {k}' for k, v in values.items())
    result = dbt(tmp_path, "UTC", "--quiet", "show", "--inline", sql, "--output", "json", "--vars", "{dataset: eu_shop}")
    assert result.returncode == 0, result.stdout + result.stderr
    shown = json.loads(result.stdout[result.stdout.index("{"):])["show"][0]
    assert shown == {"one_space": True, "two_spaces": True, "tab": True, "text": False, "empty": False}


@pytest.mark.parametrize("dataset", [d["dataset"] for d in load_datasets()])
def test_bridge_balances(dataset):
    steps = rows(ROOT / "data" / dataset / "recon.duckdb",
                 "select entity, period, label, rows, amount from main.load_bridge")
    assert steps
    through, target = Counter(), {}
    for entity, period, label, count, amount in steps:
        if label == "target":
            target[(entity, period)] = (count, amount)
        else:
            through[(entity, period, "rows")] += count
            through[(entity, period, "amount")] += amount
    assert set(target) == {(e, p) for e, p, _ in through}
    for (entity, period), (count, amount) in target.items():
        assert (through[(entity, period, "rows")], through[(entity, period, "amount")]) == (count, amount), (entity, period)


def test_october_row_holds_the_two_shifted_payments():
    moved_in = rows(ROOT / "data" / "subscribe_co" / "recon.duckdb",
                    "select rows from main.load_bridge where entity = 'payments' "
                    "and period = date '2026-10-01' and label = 'moved_in'")
    assert moved_in == [(2,)]


def build_copy(tmp_path, dataset, change):
    """Build a changed copy of a dataset with every check except the self-check, which the change breaks."""
    row = next(d for d in load_datasets() if d["dataset"] == dataset)
    data = tmp_path / "data" / dataset
    shutil.copytree(ROOT / "data" / dataset, data, ignore=shutil.ignore_patterns("recon.duckdb*"))
    change(data)
    relations = ", ".join(row["relations"].split(";"))
    result = dbt(tmp_path, "UTC", "build", "--select", "tag:load_check", "--exclude", "load_truth_match",
                 "load_truth_counts", "--vars", f"{{dataset: {dataset}, suite: load, load_relations: [{relations}]}}")
    return result, data / "recon.duckdb"


def rewrite(path, keep=lambda row: True, edit=lambda row: row):
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        header, kept = reader.fieldnames, [edit(r) for r in reader if keep(r)]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(kept)


def test_line_loaded_twice_then_deleted_is_one_extra_and_one_repeat(tmp_path):
    def delete_a_repeated_line(data):
        with (data / "target_lines.csv").open(encoding="utf-8", newline="") as f:
            twice = next(r["line_guid"] for r in csv.DictReader(f) if r["export_run"] == "2")
        rewrite(data / "source_lines.csv", keep=lambda r: r["line_guid"] != twice)
        delete_a_repeated_line.key = twice

    result, db = build_copy(tmp_path, "opt_torg", delete_a_repeated_line)
    assert result.returncode == 0, result.stdout + result.stderr
    found = rows(db, "select cause, column_name, difference from main.load_discrepancies "
                     f"where key = '{delete_a_repeated_line.key}' order by cause")
    assert found == [("deleted_left_behind", None, Decimal("1.0000")), ("duplicate_after_rerun", None, Decimal("1.0000"))]


def test_amount_lost_in_the_target_keeps_the_bridge_balanced(tmp_path):
    def empty_one_amount(data):
        with (data / "target_invoices.csv").open(encoding="utf-8", newline="") as f:
            first = next(csv.DictReader(f))["invoice_no"]
        rewrite(data / "target_invoices.csv", edit=lambda r: {**r, "amount": ""} if r["invoice_no"] == first else r)
        empty_one_amount.key = first

    result, db = build_copy(tmp_path, "subscribe_co", empty_one_amount)
    assert result.returncode == 0, result.stdout + result.stderr
    assert rows(db, "select cause, target_value from main.load_discrepancies "
                    f"where key = '{empty_one_amount.key}' and column_name = 'amount'") == [("value_mismatch", None)]


def test_amount_lost_in_the_first_copy_keeps_the_bridge_balanced(tmp_path):
    def empty_the_first_copy(data):
        with (data / "target_lines.csv").open(encoding="utf-8", newline="") as f:
            repeat = next(r for r in csv.DictReader(f) if r["export_run"] == "2")
        rewrite(data / "target_lines.csv", edit=lambda r: {**r, "amount": ""}
                if r["line_guid"] == repeat["line_guid"] and r["export_run"] == "1" else r)
        empty_the_first_copy.key, empty_the_first_copy.kept = repeat["line_guid"], Decimal(repeat["amount"])

    result, db = build_copy(tmp_path, "opt_torg", empty_the_first_copy)
    assert result.returncode == 0, result.stdout + result.stderr
    assert rows(db, "select amount_target from main.load_discrepancies "
                    f"where key = '{empty_the_first_copy.key}' and cause = 'duplicate_after_rerun'") == [
        (empty_the_first_copy.kept,)]
