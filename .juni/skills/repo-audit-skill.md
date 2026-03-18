# Skill: Project Migration & Documentation Auditor

## Role
Responsible for the global Ollama-to-vLLM migration across dependencies, documentation, and test infrastructure. This is the **coordination skill** that defines execution order and tracks overall migration progress.

## Execution Order
The full migration must be executed in this sequence:
1. **`settings-migration.md`** — Create `VllmSettings`, migrate fields from `OllamaSettings`.
2. **`vllm-infrastructure.md`** — Implement vLLM server lifecycle management.
3. **`handler-migration.md`** — Refactor `handler.py` to use the new settings and vLLM worker.
4. **`book-processing-logic.md`** — Update the post-processing logic (chunking, vision, prompts).
5. **`dockerfile-migration.md`** — Update the container build for vLLM.
6. **`repo-audit-skill.md`** (this file) — Final audit: dependencies, docs, tests, consistency.

## Task 1: Dependency Audit
Update `requirements.txt`:
- **Remove**: `ollama==0.6.1`
- **Add**:
  - `openai` — async client for vLLM's OpenAI-compatible API
  - `pydantic` — already present (`2.12.5`), verify version compatibility
  - `pydantic-settings` — already present (`2.12.0`), verify version compatibility
  - `httpx` — async HTTP client, used internally by the `openai` library for async operations
- **Do NOT add** `vllm` to `requirements.txt` — vLLM runs as a separate server process (started via subprocess), not as a Python library dependency of the worker.

## Task 2: File Rename & Cleanup
| Current File | Action | New Name |
|---|---|---|
| `ollama_worker.py` | Rewrite or replace | `vllm_worker.py` |
| `settings.py` → `OllamaSettings` class | Replace with `VllmSettings` | (same file) |
| `handler.py` → `extract_ollama_settings_from_job_input()` | Rename function | `extract_vllm_settings_from_job_input()` |

Also clean up references in:
- `GlobalConfig` fields: `ollama_models`, `ollama_log_dir` → remove or repurpose (vLLM doesn't use these paths).
- `GlobalConfig.init_environment_variables()` → remove `OLLAMA_MODELS` and `OLLAMA_LOG_DIR` env var exports.

## Task 3: Documentation Update
Scan and update the following files:
- `README.md` — Document the new vLLM-based architecture, Pydantic configuration, and all `VLLM_*` environment variables.
- `test/README.md` — Update test instructions to reflect the new setup (vLLM server, OpenAI client).
- `AGENTS.md` — Review and update if it references Ollama-specific workflows.

**Documentation must include:**
- Complete list of `VLLM_*` environment variables with types, defaults, and descriptions.
- Explanation of the sequential execution model (Marker OCR → VRAM recovery → vLLM post-processing).
- Updated architecture diagram or description.

## Task 4: Test Suite Alignment
- Update `test/test-handler.py` to use the `openai` async client instead of the `ollama` client.
- Update `test/test_handler_image_description_helpers.py` if it references `OllamaSettings`.
- Add new test coverage for:
  - `VllmSettings` validation logic (required fields, defaults, computed fields).
  - vLLM health check readiness logic.
  - Error handling when vLLM is unreachable.
- Update test env files (`test/custom.env`, `test/marker.env`, `test/tools.env`) to replace any `OLLAMA_*` variables with `VLLM_*` equivalents.

## Task 5: Consistency Sweep
After all other tasks are complete:
1. Search the entire codebase for remaining `ollama` / `Ollama` / `OLLAMA` references (case-insensitive).
2. Replace with appropriate `vllm` / `vLLM` / `VLLM` equivalents.
3. **Exceptions**: Keep historical references in git commit messages, CHANGELOG, or LICENSE files.
4. Verify no imports of the `ollama` Python package remain.
5. Verify `requirements.txt` no longer lists `ollama`.

## Task 6: Final Verification
- Run the full test suite and confirm all tests pass.
- Verify the application starts without errors in a test environment.
- Confirm `README.md` accurately reflects the current codebase.
