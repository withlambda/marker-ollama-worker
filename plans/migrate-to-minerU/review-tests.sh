#!/bin/sh
set -eu

RESULTS_FILE="${RESULTS_FILE:-/results/review-results.txt}"

record() {
  printf '\n=== %s ===\n' "$1" | tee -a "$RESULTS_FILE"
}

: > "$RESULTS_FILE"

record "Dependency check"
python check_dependencies.py 2>&1 | tee -a "$RESULTS_FILE"

record "Pytest suite"
pytest test 2>&1 | tee -a "$RESULTS_FILE"

record "Review verification completed"
