# Context
This file, `test/tools.env`, contains environment variable overrides for common Python and ML tools used within the container to ensure efficient and stable local testing.

# Interface

## Variables
- `PYTHONUNBUFFERED`: `1` (ensures logs are immediately visible).
- `HF_HUB_OFFLINE`: `1` (prevents external network calls for model metadata).
- `VLLM_PORT`: `8000`.
- `PYTORCH_ENABLE_MPS_FALLBACK`: `1`.
- `TORCH_NUM_THREADS`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS`: `1` (limits CPU thread usage during tests).

# Logic
The file is a standard shell-compatible environment file. It is used by `docker run` via the `--env-file` flag in `test/run.sh`.

# Goal
The prompt file provides the necessary tool-specific configuration to ensure a controlled and fast local test execution.
