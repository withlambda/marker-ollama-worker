#!/bin/bash

set -euo pipefail

RESULT_FILE="${RESULT_FILE:-/results/review-results.txt}"
mkdir -p "$(dirname "${RESULT_FILE}")"

{
  echo "# review-plan-implementation migrate-to-minerU"
  echo "python=$(python --version 2>&1)"
  echo "pytest=$(python -m pytest --version 2>&1)"
  echo
  echo "## import-check"
  python - <<'PY'
import json_repair
import langdetect
import mineru
import paddle
import runpod
import torch

print("imports-ok")
PY
  echo
  echo "## targeted-tests"
  python -m pytest \
    test/test_handler_settings_extraction.py \
    test/test_handler_image_description_helpers.py \
    test/test_handler_end_to_end_language.py \
    test/test_handler_language_inference.py \
    test/test_vllm_settings.py \
    test/test_vllm_worker_language_aware.py \
    test/test_vllm_worker_chunking.py \
    test/test_vllm_worker_event_loop.py \
    test/test_vllm_worker_token_budget.py \
    -v
  echo
  echo "## full-suite"
  python -m pytest test/ -v
} 2>&1 | tee "${RESULT_FILE}"
