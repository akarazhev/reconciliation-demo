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
