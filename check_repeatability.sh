#!/usr/bin/env bash
# Spec §1, criterion 4: a new company adds staging and a mapping; shared logic is the same before and after.
# Compares two commits, not the working tree, so later work on shared code does not erase the proof.
# Usage: ./check_repeatability.sh [base] [target]; default: stripe-only-initial ozon-added.
set -euo pipefail
cd "$(dirname "$0")"
base="${1:-stripe-only-initial}"
target="${2:-ozon-added}"
shared="dbt/models/core dbt/models/recon dbt/macros dbt/tests run.sh report.py"

echo "Changed from $base to $target (data excluded):"
git diff --stat "$base" "$target" -- . ':(exclude)data'
echo
echo "New or changed lines per file:"
git diff --numstat "$base" "$target" -- . ':(exclude)data' ':(exclude)uv.lock'
echo
if git diff --quiet "$base" "$target" -- $shared; then
  echo "OK: core, recon, macros, tests, run.sh and report.py are the same in $base and $target"
else
  echo "FAIL: shared logic differs between $base and $target:"
  git diff --stat "$base" "$target" -- $shared
  exit 1
fi
