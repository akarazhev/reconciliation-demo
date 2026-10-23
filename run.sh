#!/usr/bin/env bash
# Rebuild everything from scratch: data, one dbt build per dataset, the page and the dbt docs.
set -euo pipefail
cd "$(dirname "$0")"
export RECON_ROOT="$PWD"
export DBT_SEND_ANONYMOUS_USAGE_STATS=false

uv sync --frozen
uv run python generate.py

first=""
while IFS=, read -r dataset platform currency counterparty title; do
  [ "$dataset" = "dataset" ] && continue
  first="${first:-$dataset:$platform}"
  rm -f "data/$dataset/recon.duckdb" "data/$dataset/recon.duckdb.wal"
  start=$SECONDS
  uv run dbt build --project-dir dbt --profiles-dir dbt --vars "{dataset: $dataset, platform: $platform}"
  echo "$dataset: $((SECONDS - start)) s"
done < dbt/seeds/datasets.csv

# Demo 2, the load check: its own datasets and models, every time in UTC.
while IFS=, read -r dataset relations _; do
  [ "$dataset" = "dataset" ] && continue
  rm -f "data/$dataset/recon.duckdb" "data/$dataset/recon.duckdb.wal"
  start=$SECONDS
  TZ=UTC uv run dbt build --project-dir dbt --profiles-dir dbt --select tag:load_check \
    --vars "{dataset: $dataset, suite: load, load_relations: [${relations//;/, }]}"
  echo "$dataset: $((SECONDS - start)) s"
done < dbt/seeds/load/load_datasets.csv

uv run python report_load.py
uv run python report.py
dataset="${first%%:*}"
platform="${first##*:}"
# The docs are published: build them with a relative root so no local path ends up in the page.
RECON_ROOT=. uv run dbt docs generate --static --project-dir dbt --profiles-dir dbt --vars "{dataset: $dataset, platform: $platform}"
mkdir -p site/docs
cp dbt/target/static_index.html site/docs/index.html
echo "done: site/ — start pages in English and Russian, one page per company, site/docs/"
