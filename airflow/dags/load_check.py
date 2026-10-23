"""The load check as an Airflow Dag: generate the data, build each dataset, write the pages.

The tasks and their commands come from load_tasks.py, the list the page draws too. Each runs from the repository
root with the demo's own uv environment, so the Airflow environment needs nothing of the demo's.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG, chain

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import load_tasks  # noqa: E402  the repository root is on the path only from here

with DAG(
    dag_id="load_check",
    schedule=None,
    start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
    catchup=False,
):
    chain(*[
        BashOperator(
            task_id=task_id,
            bash_command=command,
            cwd=str(ROOT),
            env={"RECON_ROOT": str(ROOT), "TZ": "UTC", "DBT_SEND_ANONYMOUS_USAGE_STATS": "false"},
            append_env=True,
        )
        for task_id, command in load_tasks.dag_tasks()
    ])
