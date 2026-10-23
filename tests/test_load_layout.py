"""Demo 2 nodes exist only in a load check run; a demo 1 run does not see them."""
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOAD_PATHS = ("seeds/load/", "models/load/", "models/staging/subscribe_co/", "models/staging/opt_torg/", "tests/load/")


def dbt_ls(tmp_path: Path, dataset: str, dbt_vars: str, *selection: str) -> list[str]:
    """The original file path of every node `dbt ls` lists for these vars."""
    (tmp_path / "data" / dataset).mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "RECON_ROOT": str(tmp_path), "DBT_SEND_ANONYMOUS_USAGE_STATS": "false"}
    result = subprocess.run(
        ["dbt", "--quiet", "ls", "--project-dir", str(ROOT / "dbt"), "--profiles-dir", str(ROOT / "dbt"),
         "--target-path", str(tmp_path / "target"), "--log-path", str(tmp_path / "logs"),
         "--output", "json", "--output-keys", "name", "original_file_path", "--vars", dbt_vars, *selection],
        env=env, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    return [json.loads(line)["original_file_path"] for line in result.stdout.splitlines() if line.startswith("{")]


def test_demo1_parse_sees_no_load_nodes(tmp_path):
    paths = dbt_ls(tmp_path, "eu_shop", "{dataset: eu_shop, platform: stripe}",
                   "--resource-type", "seed", "--resource-type", "model", "--resource-type", "test")
    assert paths
    assert [p for p in paths if p.startswith(LOAD_PATHS)] == []


def test_load_selection_lists_only_load_nodes(tmp_path):
    paths = dbt_ls(tmp_path, "subscribe_co", "{dataset: subscribe_co, suite: load, load_relations: []}",
                   "--select", "tag:load_check")
    assert paths
    assert [p for p in paths if not p.startswith(LOAD_PATHS)] == []


DATASET_WORDS = ("subscribe_co", "opt_torg", "customer_no", "customer_id", "invoice_no", "payment_id", "paid_at",
                 "issued_at", "status_code", "channel", "batch_no", "address_line2", "doc_guid", "line_guid",
                 "payment_guid", "invoice_guid", "customer_inn", "doc_date", "pay_date", "modified_at", "article",
                 "export_night", "export_run", "exported_at", "old_article", "new_article")


def test_macros_models_and_tests_name_no_dataset():
    pattern = re.compile(r"\b(" + "|".join(DATASET_WORDS) + r")\b")
    shared = [p for folder in ("dbt/macros/load_check", "dbt/models/load", "dbt/tests/load")
              for p in sorted((ROOT / folder).iterdir()) if p.is_file()]
    assert shared
    found = [(p.name, m.group(0)) for p in shared for m in pattern.finditer(p.read_text(encoding="utf-8"))]
    assert found == []
