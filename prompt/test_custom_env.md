# Context
This file, `test/custom.env`, defines the core environment variables for the local integration test. it configures the volume mount paths, the test handler entry point, and the VRAM/vLLM settings for the test run.

# Interface

## Variables
- `VOLUME_ROOT_MOUNT_PATH`: Set to `/v` (matching the Docker volume mount).
- `HANDLER_FILE_NAME`: Set to `test-handler.py`.
- `USE_POSTPROCESS_LLM`: Set to `false` for basic testing (can be toggled for full integration).
- `MARKER_DEBUG`: `true`.
- `VLLM_MODEL_PATH`: Path to the test model (e.g., `unsloth/SmolLM2-135M-Instruct-GGUF`).
- `VRAM_GB_TOTAL`: `8`.
- `VLLM_VRAM_GB_MODEL`: `6`.
- `VLLM_GPU_UTIL`: `0.90`.
- `VLLM_PORT`: `8000`.

# Logic
The file is a standard shell-compatible environment file. It is used by `docker run` via the `--env-file` flag in `test/run.sh`.

# Goal
The prompt file captures the specific environment overrides required to run the worker in a local test mode.
