"""Unknown report categories must fail even when their monetary amount is zero."""
import csv
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("amount", ["0.00", "10.00"])
def test_stripe_rejects_unknown_categories_including_zero_amount(tmp_path, amount):
    data = tmp_path / "data" / "guard"
    data.mkdir(parents=True)
    source = ROOT / "data" / "eu_shop" / "stripe_balance.csv"
    shutil.copyfile(source, data / source.name)
    with source.open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    row.update(balance_transaction_id="txn_unknown", reporting_category="topup",
               gross=amount, fee="0.00", net=amount)
    with (data / source.name).open("a", encoding="utf-8", newline="") as handle:
        csv.DictWriter(handle, fieldnames=list(row), lineterminator="\n").writerow(row)
    env = {**os.environ, "RECON_ROOT": str(tmp_path), "DBT_SEND_ANONYMOUS_USAGE_STATS": "false"}
    result = subprocess.run(
        ["dbt", "build", "--project-dir", str(ROOT / "dbt"), "--profiles-dir", str(ROOT / "dbt"),
         "--target-path", str(tmp_path / "target"), "--log-path", str(tmp_path / "logs"),
         "--vars", "{dataset: guard, platform: stripe}", "--select",
         "stg_stripe__payout_items", "stg_stripe__lines", "kind_map_stripe"],
        env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "Unknown Stripe reporting_category: topup" in result.stdout + result.stderr
