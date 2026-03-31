# Implementation Status — Migrate from Marker-PDF to MinerU

## Overall Status: ✅ Complete

All five tasks have been implemented and verified.

## Task Summary

| Task | Status | Notes |
|------|--------|-------|
| 01 — Dockerfile Overhaul | ✅ Done | MinerU + PaddlePaddle base, model downloads via `huggingface-cli`, `mineru.json` generated at build time, and runtime dependencies now aligned around `mineru[pipeline]==3.0.1`. |
| 02 — Refactor Settings | ✅ Done | `MarkerSettings` → `MinerUSettings`, `MINERU_*` env prefix, removed marker-only fields, added `ocr_mode`/`output_format`. |
| 03 — Refactor Python Handler | ✅ Done | MinerU 3.0.1 pipeline integration via `mineru.cli.common.do_parse(...)`, `mp.Pool` parallelism, and normalized Markdown/image output handling. |
| 04 — Update References and Docs | ✅ Done | README.md, check_dependencies.py, env files, config/download-models, and release automation updated. `surya.env` removed. |
| 05 — Update Tests | ✅ Done | All test files migrated to MinerU naming, regression tests added, settings extraction test added. |

## Review Fixes (review-plan-implementation pass)

The following issues were identified and fixed during the post-implementation review:

### 1. Removed Forbidden Test Dependency Shims
- **Issue**: The prior review introduced `test/conftest.py` session hooks that injected fake `runpod`, `torch`, `mineru`, and `paddle` modules into `sys.modules`. That contradicted both Task 05 and the project guardrails, which require real third-party dependencies for local test execution.
- **Fix**: Replaced `test/conftest.py` with a minimal, no-op configuration file that explicitly documents the real-dependency requirement and allows collection to fail fast when the test environment is incomplete.
- **Files**: `test/conftest.py`

### 2. Restored Fail-Fast Required Dependency Imports in `handler.py`
- **Issue**: `handler.py` treated `paddle` as optional via `try/except ImportError`, masking incomplete environments even though `paddle` is a required runtime dependency for the MinerU worker.
- **Fix**: Switched back to a direct `import paddle` so missing dependencies fail immediately and consistently with the migration plan.
- **Files**: `handler.py`

### 3. Improved Worker Cleanup Error Logging
- **Issue**: Cleanup failures in `mineru_worker_exit()` were logged without stack traces, making VRAM shutdown problems harder to diagnose.
- **Fix**: Added contextual cleanup logging with `exc_info=True`.
- **Files**: `handler.py`

### 4. Existing Test Migration Cleanups Preserved
- **Issue**: The migrated test package still needed its MinerU naming cleanup and extraction test alignment.
- **Fix**: Kept the existing `test/test_handler_settings_extraction.py` and `test/__init__.py` updates while removing the invalid shim-based test bootstrap introduced later.
- **Files**: `test/test_handler_settings_extraction.py`, `test/__init__.py`

### 5. Corrected MinerU 3.0.1 API Usage
- **Issue**: The implementation still referenced the older `PymuDocDataset` / `doc_analyze` flow, but the installed `mineru==3.0.1` package exposes the supported sync pipeline via `mineru.cli.common.do_parse(...)` instead.
- **Fix**: Reworked `mineru_process_single_file()` to call `do_parse(...)` with the configured OCR mode and then normalize the generated Markdown/images back into the worker’s expected output layout.
- **Files**: `handler.py`

### 6. Fixed the Runtime Dependency Specification
- **Issue**: `requirements.txt` used `mineru[full]==3.0.1`, but MinerU 3.0.1 does not publish a `full` extra. That left required pipeline dependencies such as `shapely` uninstalled while still making the dependency check look superficially healthy.
- **Fix**: Switched the project to `mineru[pipeline]==3.0.1`, added explicit dependency verification for `shapely`, and updated `release.sh` to keep the correct dependency line in sync for future releases.
- **Files**: `requirements.txt`, `check_dependencies.py`, `release.sh`

### 7. Added Support for Missing MinerU Settings
- **Issue**: `page_range` and `disable_image_extraction` settings were defined in `MinerUSettings` but were not being passed to the `do_parse` function in `handler.py`.
- **Fix**: Added `_parse_mineru_page_range` helper to handle page range parsing (0-indexed per MinerU API) and updated `mineru_process_single_file` to pass `start_page_id` and `end_page_id`. Implemented `disable_image_extraction` by conditionally removing the `images` subfolder during normalization.
- **Files**: `handler.py`

### 8. Fixed Inconsistent Setting Names in Documentation
- **Issue**: `README.md` used `mineru_force_ocr` while the implementation used `mineru_ocr_mode`.
- **Fix**: Updated `README.md` to use `mineru_ocr_mode` and documented the new MinerU-specific fields.
- **Files**: `README.md`

## Test Results

Verification was completed during this review pass with the following steps:

1. **Reusable Linux review image**
   - Commands:
     - `docker build -f plans/migrate-to-minerU/review-test.Dockerfile -t notelm-mineru-review .`
     - `docker build -f plans/migrate-to-minerU/review-test-overlay.Dockerfile -t notelm-mineru-review-overlay .`
   - Result: Built a reusable review environment plus a lightweight overlay image that adds the missing MinerU pipeline extras required by the current review.

2. **Grouped in-container verification**
   - Command: `docker run --rm -v "$PWD":/workspace -w /workspace -e RESULTS_FILE=/workspace/plans/migrate-to-minerU/review-results.txt notelm-mineru-review-overlay sh /workspace/plans/migrate-to-minerU/review-tests.sh`
   - Result:
     - `check_dependencies.py` passed, including `mineru`, `paddle`, `shapely`, and the vLLM entrypoint import check.
     - Full relevant pytest suite passed: `79 passed`.

3. **Conclusion**
   - The review fixes applied in this pass are verified in a real Linux dependency environment, and the migration now matches the implemented/tested MinerU 3.0.1 pipeline behavior.

## Remaining Marker References (Verified False Positives)

A project-wide grep confirms no stale marker-pdf references remain. The following are intentional:
- `handler.py`: "markers" / "start/end marker" in docstrings referring to image description delimiters
- `settings.py`: "page markers" in the vLLM prompt template
- `models/*/vocab.txt`: OCR model vocabulary entries (not application code)
