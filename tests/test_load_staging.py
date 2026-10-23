"""Staging of the billing migration: Helsinki time made UTC, single spaces kept, unknown values stop the build."""
import csv
import datetime as dt
import os
import shutil
import subprocess
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "subscribe_co"


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def query(sql):
    db = DATA / "recon.duckdb"
    if not db.exists():
        pytest.skip("run ./run.sh first")
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_manual_paid_at_is_converted_from_helsinki():
    local = {r["payment_id"]: dt.datetime.fromisoformat(r["paid_at"])
             for r in read(DATA / "legacy_payments.csv") if r["channel"] == "manual"}
    staged = dict(query("select payment_id, paid_at from main.stg_subscribe_co__payments_source "
                        "where channel = 'manual'"))
    assert len(local) == 25
    assert staged == {key: value - dt.timedelta(hours=3) for key, value in local.items()}


@pytest.mark.parametrize(("file", "column", "value", "model"), [
    ("legacy_invoices.csv", "status_code", "X", "stg_subscribe_co__invoices_source"),
    ("legacy_payments.csv", "channel", "crypto", "stg_subscribe_co__payments_source"),
    ("legacy_invoices.csv", "status_code", "", "stg_subscribe_co__invoices_source"),
    ("legacy_payments.csv", "channel", "", "stg_subscribe_co__payments_source"),
    ("target_customers.csv", "customer_id", "", "stg_subscribe_co__customers_target"),
    ("target_invoices.csv", "customer_id", "", "stg_subscribe_co__invoices_target"),
])
def test_unknown_values_stop_the_build(tmp_path, file, column, value, model):
    data = tmp_path / "data" / "subscribe_co"
    shutil.copytree(DATA, data, ignore=shutil.ignore_patterns("recon.duckdb*"))
    first = read(data / file)[0]
    key = next(iter(first))
    row = {**first, key: first[key] + "-new", column: value}
    with (data / file).open("a", encoding="utf-8", newline="") as f:
        csv.DictWriter(f, fieldnames=list(row), lineterminator="\n").writerow(row)
    env = {**os.environ, "RECON_ROOT": str(tmp_path), "TZ": "UTC", "DBT_SEND_ANONYMOUS_USAGE_STATS": "false"}
    result = subprocess.run(
        ["dbt", "build", "--project-dir", str(ROOT / "dbt"), "--profiles-dir", str(ROOT / "dbt"),
         "--target-path", str(tmp_path / "target"), "--log-path", str(tmp_path / "logs"),
         "--vars", "{dataset: subscribe_co, suite: load, load_relations: []}", "--select", model, "expected_codes"],
        env=env, capture_output=True, text=True, timeout=120)
    assert result.returncode != 0, result.stdout + result.stderr
    assert f"Unknown subscribe_co {column}: {value or 'NULL'}" in result.stdout + result.stderr


def test_address_line2_keeps_a_single_space():
    rows = query("select count(*) from main.stg_subscribe_co__customers_source where address_line2 = ' '")
    assert rows == [(10,)]
