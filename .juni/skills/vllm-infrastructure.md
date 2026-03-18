# Skill: vLLM Infrastructure Architect

## Role
Specialist in GPU memory orchestration and vLLM lifecycle management on RunPod using Pydantic for configuration. This skill is GPU-agnostic — VRAM limits are driven by the existing `VRAM_GB_TOTAL` environment variable in `GlobalConfig`.

## Scope
This skill covers **only** vLLM server startup, shutdown, health verification, and GPU resource management. It does **not** cover settings migration (see `settings-migration.md`), handler refactoring (see `handler-migration.md`), or Dockerfile changes (see `dockerfile-migration.md`).

## Prerequisites
- `settings-migration.md` must be completed first so that `VllmSettings` exists.
- The `openai` Python package must be available (added by `repo-audit-skill.md`).

## Configuration (Pydantic-Settings)
The vLLM-specific settings live in a new `VllmSettings(BaseSettings)` class (defined in `settings-migration.md`). Key infrastructure fields used by this skill:

| Field | Type | Default | Purpose |
|---|---|---|---|
| `vllm_model_path` | `DirectoryPath` | *required* | Path to the model weights directory |
| `vllm_gpu_util` | `float` | `0.90` | Max fraction of GPU memory vLLM may use |
| `vllm_max_model_len` | `int` | `16384` | Maximum sequence length |
| `vllm_max_num_seqs` | `int` | `16` | Maximum concurrent sequences |
| `vllm_port` | `int` | `8000` | Port for vLLM's OpenAI-compatible API |
| `vllm_host` | `str` | `http://127.0.0.1:8000` | Full base URL for the vLLM server |
| `vllm_startup_timeout` | `int` | `120` | Seconds to wait for vLLM readiness |
| `vllm_vram_recovery_delay` | `int` | `10` | Seconds to wait after Marker exits before starting vLLM (allows GPU memory release) |

## Server Lifecycle

### 1. VRAM Recovery Phase
- After Marker's OCR phase completes, wait `vllm_vram_recovery_delay` seconds before initializing vLLM.
- **Rationale**: GPU memory may not be released instantly after Marker exits; the delay prevents OOM during vLLM startup.
- This delay should be configurable via `VLLM_VRAM_RECOVERY_DELAY` env var.

### 2. vLLM Server Startup
- Launch vLLM as a subprocess using `subprocess.Popen()` (not `subprocess.run()`) so the main process can monitor and interact with it.
- Pass configuration from `VllmSettings` as CLI arguments to the vLLM server process.
- Capture stdout/stderr for logging.

### 3. Health Check & Readiness
- After starting vLLM, poll the health endpoint: `GET http://localhost:{vllm_port}/health`
- Retry every 2 seconds until either:
  - The endpoint returns HTTP 200 → proceed.
  - `vllm_startup_timeout` seconds elapse → raise an error and terminate the subprocess.
- **Only after the health check passes** should the worker begin sending LLM requests.

### 4. Client Communication
- Use `openai.AsyncOpenAI(base_url=f"http://localhost:{vllm_port}/v1")` to communicate with vLLM.
- vLLM exposes an OpenAI-compatible API — all chat/completion calls should use the `openai` Python client, not raw HTTP.

### 5. Graceful Shutdown
- After all LLM post-processing is complete, terminate the vLLM subprocess.
- Send `SIGTERM`, wait up to 10 seconds, then `SIGKILL` if still running.
- Log the shutdown result.

## Process Handoff & Immutability
- **Sequential Execution**: Marker OCR runs first, then vLLM post-processing. They never run concurrently.
- **Functional Pattern**: The `VllmSettings` configuration object must remain immutable throughout the app lifecycle. Treat vLLM server startup as a controlled side-effect.
- **VRAM Budget**: Use `GlobalConfig.vram_gb_total` and `GlobalConfig.vram_gb_reserve` for VRAM calculations, keeping the approach consistent with the existing `num_parallel` calculation pattern in `OllamaSettings`.

## Error Handling
- If vLLM fails to start (health check timeout), log the subprocess stderr and raise a clear error.
- If vLLM crashes mid-processing, detect via subprocess poll, log the error, and attempt one restart before failing the job.
