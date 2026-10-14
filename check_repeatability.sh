#!/usr/bin/env bash
# Spec §1, criterion 4: the second company adds staging and a mapping; shared logic stays as tagged.
set -euo pipefail
cd "$(dirname "$0")"
base="${1:-stripe-only}"
shared="dbt/models/core dbt/models/recon dbt/macros dbt/tests run.sh report.py"

echo "Changed since $base (data excluded):"
git diff --stat "$base" -- . ':(exclude)data'
echo
echo "New or changed lines per file:"
git diff --numstat "$base" -- . ':(exclude)data' ':(exclude)uv.lock'
echo
if git diff --quiet "$base" -- $shared && [ -z "$(git ls-files --others --exclude-standard -- $shared)" ]; then
  echo "OK: core, recon, macros, tests, run.sh and report.py are unchanged since $base"
else
  echo "FAIL: shared logic changed since $base:"
  git diff --stat "$base" -- $shared
  git ls-files --others --exclude-standard -- $shared
  exit 1
fi
