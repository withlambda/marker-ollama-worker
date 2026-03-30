# Task 05 — Update Tests

## Dependencies
- Task 02 (Refactor Settings)
- Task 03 (Refactor Python Handler)
- Task 04 (Update References and Docs)

## Requirements Traced
- NFR-4 (Test Coverage)
- FR-6 (Naming Consistency)

## Exact Test Inventory to Audit

The following existing files must be reviewed using their exact current repository names:

- `test/test-handler.py` (container test harness / entrypoint, not a pytest module)
- `test/test_handler_language_inference.py`
- `test/test_handler_image_description_helpers.py`
- `test/test_handler_end_to_end_language.py`
- `test/test_vllm_worker_language_aware.py`
- `test/test_vllm_settings.py`
- `test/test_vllm_worker_chunking.py`
- `test/test_vllm_worker_event_loop.py`
- `test/test_vllm_worker_token_budget.py`
- `test/run.sh`
- `test/marker.env` → `test/mineru.env`
- `test/custom.env`
- `test/tools.env`
- `test/create-sample-pdfs.py`

## Implementation Steps

### 0. Prepare Real Test Dependencies (Avoid Redundant Downloads)

To prevent multiple multi-GB downloads during test preparation:

- **Check for existing dependencies** on the host before running `pip install`:
  ```bash
  if ! python3 -c "import mineru; import paddle" 2>/dev/null; then
    python -m pip install -r requirements.txt
  fi
  if ! python3 -m pytest --version 2>/dev/null; then
    python -m pip install -r test/requirements-setup.txt
  fi
  ```
- **Prefer running tests inside the `markllm-mineru-test` container** built in Task 01:
  - This image already contains all heavy dependencies (`mineru[full]==3.0.1`, `paddlepaddle-gpu==3.3.0`, `vllm==0.18.0`).
  - Use `docker run --rm -v $(pwd):/app markllm-mineru-test python -m pytest test/ -v` to run the full suite.
- Do not use dummy `sys.modules` shims for required third-party packages (`mineru`, `paddle`).

### 1. Update `test/test-handler.py`

- Replace `marker_*` job input keys with `mineru_*` equivalents:
  - `"marker_workers"` → `"mineru_workers"`
  - `"marker_paginate_output"` → remove (no MinerU equivalent)
  - `"marker_force_ocr"` → removed (replaced by `"mineru_force_ocr"` with values `"ocr"`, `"txt"`, `"auto"`)
  - `"marker_disable_multiprocessing"` → remove (no MinerU equivalent)
- Update any comments referencing marker.

### 2. Update `test/test_handler_language_inference.py`

- Remove marker-specific module-shim bootstrapping.
- Import `handler.py` with real installed dependencies, then patch behavior-level call sites (e.g., `doc_analyze`, dataset method calls, or wrapper helpers) as needed for deterministic unit tests.
- Update assertions that reference marker function names or return values.

### 3. Update `test/test_handler_image_description_helpers.py`

- Remove `marker.*`/`mineru.*` import shims and dummy converter/config classes.
- Keep these tests engine-agnostic by targeting only the helper functions (`list_extracted_images_for_output_file`, `insert_image_descriptions_to_text_file`) while using normal module imports.
- Update any test text that says "marker" (e.g., `"Original marker text without tags."`) — this is test fixture text referring to "marker" as in "description marker", not marker-pdf. Verify intent before changing.

### 4. Update `test/test_handler_end_to_end_language.py`

- Remove marker module shims and keep only behavior-level patches/mocks after importing real dependencies.
- Note: The `begin_marker` / `end_marker` keys in localized labels refer to image description markers, NOT marker-pdf. These must NOT be renamed.
- Update any references to `extract_marker_settings_from_job_input` → `extract_mineru_settings_from_job_input`.

### 5. Update `test/test_vllm_worker_language_aware.py`

- Remove marker module shims and keep only behavior-level patches/mocks after importing real dependencies.

### 6. Update `test/test_vllm_settings.py`

- Check if this file references `MarkerSettings` — if so, update to `MinerUSettings`.
- Update any `MARKER_*` environment variable references to `MINERU_*`.

### 7. Update `test/run.sh`

- If the script sources `marker.env`, update to source `mineru.env`.
- Update any `MARKER_*` variable exports.
- Rename the Docker container name from `"marker-with-vllm-test"` (line 43) to `"mineru-with-vllm-test"` or equivalent.
- Update comments referencing marker.

### 8. Update `test/create-sample-pdfs.py`

- Update the comment on line 43 (`# Define the output directory as the input dir for the further marker-pdf`) to reference MinerU.

### 9. Verify Unchanged Test Files

The following test files exist in the `test/` directory and are not expected to require changes. Verify each contains no `marker` references (excluding `begin_marker`/`end_marker` description labels):
- `test/test_vllm_worker_chunking.py`
- `test/test_vllm_worker_event_loop.py`
- `test/test_vllm_worker_token_budget.py`

If any of these files contain marker-pdf references, update them accordingly.

### 10. Add `extract_mineru_settings_from_job_input()` Integration Test

- This test was deferred from Task 02 because the function is implemented in Task 03.
- Write a test that verifies `extract_mineru_settings_from_job_input()` correctly parses `mineru_*` prefixed keys from job input and produces a valid `MinerUSettings` instance.
- Include cases for: valid overrides, unknown keys (should warn), and empty input.

### 11. Add Regression Coverage for Migration-Specific Risks

- These regressions are **required**, not optional, because they cover the highest-risk behavioral differences in the migration.
- Add/extend a test that runs a fixed two-column PDF fixture and asserts deterministic reading-order anchors in output Markdown.
- Add/extend a contract test that verifies MinerU-style image references are discoverable by `list_extracted_images_for_output_file()` and correctly handled by `insert_image_descriptions_to_text_file()`.
- The contract test must use the real, verified MinerU output pattern from Task 03 rather than an assumed placeholder layout.

### 12. Run All Tests

Run targeted migration-related tests first, then execute the full test suite. 

**Option A: Inside the test container (Recommended to avoid local downloads)**:
```bash
docker run --rm \
  -v $(pwd):/app \
  -v $(pwd)/test/mineru.env:/app/mineru.env \
  markllm-mineru-test python3 -m pytest test/ -v
```

**Option B: On the host (Only if dependencies were prepared in Step 0)**:
```bash
python -m pytest test/ -v
```

If any tests fail due to MinerU API differences (e.g., different return types), update behavior-level test patches and assertions accordingly.

## Test Requirements
- Dependencies are installed from `requirements.txt` and `test/requirements-setup.txt` before test execution.
- All existing test files must pass after the MinerU migration updates.
- No test file should contain references to `marker.*` modules (except `begin_marker`/`end_marker` for image description labels).
- No test should rely on dummy `sys.modules` injection for required dependencies (`mineru`, `paddle`).
- Regression coverage exists for two-column reading order and MinerU image-path compatibility, based on the verified Task 03 output contract.
- `extract_mineru_settings_from_job_input()` integration with `MinerUSettings` is tested (deferred from Task 02).
- `test/run.sh` must execute without errors when the environment is properly configured.
