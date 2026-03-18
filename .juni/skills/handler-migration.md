# Skill: Handler Migration — Ollama to vLLM

## Role
Responsible for refactoring `handler.py` (663 lines, main entry point) and replacing `ollama_worker.py` with a new `vllm_worker.py`. This skill bridges the settings layer (`settings-migration.md`) and the infrastructure layer (`vllm-infrastructure.md`) into the application's request-handling flow.

## Prerequisites
- `settings-migration.md` must be completed (`VllmSettings` class exists).
- `vllm-infrastructure.md` must be completed (server lifecycle defined).

## Scope
- Modify `handler.py`.
- Delete `ollama_worker.py`.
- Create `vllm_worker.py`.
- Update `utils.py` if it contains Ollama-specific helpers.

## Task 1: Replace `ollama_worker.py` with `vllm_worker.py`

### Current State (`ollama_worker.py`)
The existing worker uses the `ollama` Python client to:
- Start/stop the Ollama server process.
- Build models from Hugging Face weights.
- Send text correction and image description requests.

### New `vllm_worker.py` Must Provide
1. **`start_vllm_server(settings: VllmSettings) -> subprocess.Popen`**
   - Launch vLLM as a subprocess with CLI args derived from `VllmSettings`.
   - Wait for health check (`GET /health`) with configurable timeout.
   - Return the subprocess handle for later shutdown.

2. **`stop_vllm_server(process: subprocess.Popen) -> None`**
   - Send `SIGTERM`, wait up to 10 seconds, then `SIGKILL`.
   - Log shutdown status.

3. **`correct_text_chunk(client: AsyncOpenAI, model: str, system_prompt: str, chunk: str) -> str`**
   - Send a single chunk for OCR correction via the OpenAI-compatible API.
   - Return the corrected text.
   - Raise on failure (caller handles retries).

4. **`describe_image(client: AsyncOpenAI, model: str, prompt: str, image_path: Path) -> str`**
   - Send an image for multimodal description.
   - Encode the image as base64 and send via the vision API.
   - Return the description text.

5. **`process_chunks(client: AsyncOpenAI, settings: VllmSettings, chunks: List[str], system_prompt: str) -> List[str]`**
   - Orchestrate parallel chunk correction using `asyncio` with `chunk_workers` concurrency.
   - Handle retries per chunk (`max_retries`, `retry_delay`).
   - On final failure, preserve the original chunk text and log a warning.

## Task 2: Refactor `handler.py`

### Function Renames
| Current Name | New Name |
|---|---|
| `extract_ollama_settings_from_job_input()` | `extract_vllm_settings_from_job_input()` |

### Function Signature Changes
- `extract_vllm_settings_from_job_input(app_config: GlobalConfig, job_input: Dict) -> VllmSettings`
  - Must construct `VllmSettings` instead of `OllamaSettings`.
  - Filter job input keys for `VLLM_*` prefixed overrides.

### Main `handler()` Flow Changes
The main `handler(job)` function currently follows this sequence:
1. Parse job input → extract settings.
2. Run Marker OCR.
3. Start Ollama server.
4. Post-process with Ollama (text correction + image descriptions).
5. Stop Ollama server.
6. Return results.

**Updated flow:**
1. Parse job input → extract `GlobalConfig`, `MarkerSettings`, `VllmSettings`.
2. Run Marker OCR (unchanged).
3. **Wait `vllm_vram_recovery_delay` seconds** (new — allows GPU memory release).
4. **Start vLLM server** via `vllm_worker.start_vllm_server()`.
5. **Create `AsyncOpenAI` client** pointing to `http://localhost:{vllm_port}/v1`.
6. Post-process with vLLM (text correction + image descriptions) via `vllm_worker` functions.
7. **Stop vLLM server** via `vllm_worker.stop_vllm_server()`.
8. Return results.

### Import Changes
```python
# Remove
from ollama_worker import ...

# Add
from vllm_worker import start_vllm_server, stop_vllm_server, process_chunks, describe_image
from openai import AsyncOpenAI
```

### Error Handling
- Wrap the vLLM lifecycle (steps 4–7) in a `try/finally` to ensure the vLLM subprocess is always terminated, even if processing fails.
- If `use_postprocess_llm` is `False` in `GlobalConfig`, skip the entire vLLM phase (steps 3–7).

## Task 3: Update `utils.py`
- Review `utils.py` for any Ollama-specific helper functions or references.
- Update or remove as needed.
- Keep all utility functions that are LLM-backend-agnostic.

## Testing Considerations
- After this migration, `test/test-handler.py` will need updates (covered by `repo-audit-skill.md` Task 4).
- The new `vllm_worker.py` should be testable in isolation with a mock `AsyncOpenAI` client.
