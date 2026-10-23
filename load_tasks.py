"""The load check's tasks, in order, as the Airflow Dag runs them and the page draws them.

Reads only dbt/seeds/load/load_datasets.csv, so the Dag's own environment needs nothing of the demo's.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def datasets() -> list[dict]:
    with (ROOT / "dbt" / "seeds" / "load" / "load_datasets.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def dag_tasks() -> list[tuple[str, str]]:
    """(task id, bash command run from the repository root) for every task of the Dag."""
    tasks = [("generate", "uv run python generate.py")]
    for d in datasets():
        dataset, relations = d["dataset"], ", ".join(d["relations"].split(";"))
        tasks.append((f"dbt_build_{dataset}",
                      f"rm -f data/{dataset}/recon.duckdb data/{dataset}/recon.duckdb.wal && "
                      f"TZ=UTC uv run dbt build --project-dir dbt --profiles-dir dbt --select tag:load_check "
                      f'--vars "{{dataset: {dataset}, suite: load, load_relations: [{relations}]}}"'))
    tasks.append(("report", "uv run python report_load.py"))
    return tasks
