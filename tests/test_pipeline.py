"""End-to-end checks over the databases ./run.sh leaves behind; skipped before the first run."""
import csv
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]


def datasets():
    with (ROOT / "dbt" / "seeds" / "datasets.csv").open(encoding="utf-8", newline="") as f:
        return [r["dataset"] for r in csv.DictReader(f)]


def connect(dataset):
    db = ROOT / "data" / dataset / "recon.duckdb"
    if not db.exists():
        pytest.skip("run ./run.sh first")
    return duckdb.connect(str(db), read_only=True)


@pytest.mark.parametrize("dataset", datasets())
def test_pipeline_found_exactly_what_was_planted(dataset):
    con = connect(dataset)
    found = con.execute("select level, cause, key, kind, difference from main.discrepancies").fetchall()
    with (ROOT / "data" / dataset / "truth.csv").open(encoding="utf-8", newline="") as f:
        planted = [(r["level"], r["cause"], r["key"], r["kind"], Decimal(r["difference"])) for r in csv.DictReader(f)]
    assert sorted(found) == sorted(planted)


def test_ozon_amounts_parse_exactly():
    con = connect("ozon_seller")
    total_db = con.execute("select sum(amount) from main.stg_ozon__accruals").fetchone()[0]
    with (ROOT / "data" / "ozon_seller" / "ozon_report.csv").open(encoding="utf-8", newline="") as f:
        total_csv = sum((Decimal(r["Сумма итого, руб."].replace(",", ".")) for r in csv.DictReader(f, delimiter=";")),
                        Decimal("0"))
    assert total_db == total_csv
