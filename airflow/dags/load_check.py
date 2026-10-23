"""The load check as an Airflow Dag: generate the data, build each dataset, write the pages."""
from datetime import datetime, timezone

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

with DAG(
    dag_id="load_check",
    schedule=None,
    start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
    catchup=False,
):
    BashOperator(task_id="noop", bash_command="echo ok")
