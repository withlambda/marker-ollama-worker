# Task 02 — Refactor Settings

## Dependencies
- Task 01 (Dockerfile Overhaul) — MinerU dependency direction and env prefix strategy are established first.

> **Execution note**: This task must be completed before Task 03 (Refactor Python Handler) so the handler refactor can consume `MinerUSettings` directly.

## Requirements Traced
- FR-3 (Multiprocessing Architecture Preserved — VRAM calculation fields)
- FR-6 (Naming Consistency)
- NFR-3 (Backward-Compatible Job Input API)
- EC-3 (MinerU API Differences — remove unsupported fields)

## Implementation Steps

### 1. Rename `MarkerSettings` → `MinerUSettings` in `settings.py`

- Rename the class from `MarkerSettings` to `MinerUSettings`.
- Update the `model_config` env prefix from `MARKER_` to `MINERU_`.
- Update the class docstring to describe MinerU configuration.
- Update the module-level docstring to reference MinerU instead of marker.

### 2. Update Fields

**Keep (rename env alias)**:
| Old Field | New Field | New Env Alias |
|:----------|:----------|:--------------|
| `workers` | `workers` | `MINERU_WORKERS` |
| `disable_image_extraction` | `disable_image_extraction` | `MINERU_DISABLE_IMAGE_EXTRACTION` |
| `page_range` | `page_range` | `MINERU_PAGE_RANGE` |
| `output_format` | `output_format` | `MINERU_OUTPUT_FORMAT` (keep as no-op; validate only `"markdown"` is accepted since MinerU always outputs Markdown) |
| `vram_gb_per_worker` | `vram_gb_per_worker` | `MINERU_VRAM_GB_PER_WORKER` |
| `debug` | `debug` | `MINERU_DEBUG` |
| `disable_maxtasksperchild` | `disable_maxtasksperchild` | `MINERU_DISABLE_MAXTASKSPERCHILD` |
| `maxtasksperchild` | `maxtasksperchild` | `MINERU_MAXTASKSPERCHILD` |

**Remove (no MinerU equivalent)**:
- `paginate_output` — MinerU does not support output pagination.
- `processors` — MinerU does not have a configurable processor pipeline.
- `disable_multiprocessing` — MinerU's internal multiprocessing is not user-configurable in the same way.
- `force_ocr` — Removed (replaced by `ocr_mode` field).

**Add (MinerU-specific)**:
- `ocr_mode` (Optional[str]) — MinerU supports different OCR modes: `"ocr"` (force OCR on all pages), `"txt"` (extract text directly), `"auto"` (auto-detect). Default: `"auto"`. Env alias: `MINERU_OCR_MODE`.

### 3. Update All Imports of `MarkerSettings`

- In `handler.py` and other modules: `from settings import MarkerSettings` → `from settings import MinerUSettings`.
- In any test files that import `MarkerSettings`.

### 4. Update `GlobalConfig` References

- The `GlobalConfig` class itself has no marker-specific fields, but its docstring references "marker" in context descriptions. Update those references to "MinerU".
- The `vram_gb_reserve` and `vram_gb_per_token_factor` docstrings may reference "marker workers" — update to "MinerU workers".

### 5. Verify `default_factory` Pattern for `maxtasksperchild`

- The current `MarkerSettings.maxtasksperchild` field uses a `default_factory` lambda that references `data["disable_maxtasksperchild"]`. After renaming the class to `MinerUSettings`, verify this pattern still works correctly:
  - Confirm the lambda closure resolves field references by name (not by class-level binding).
  - Write a unit test that instantiates `MinerUSettings` with `disable_maxtasksperchild=False` and verifies `maxtasksperchild` defaults to `25`.
  - Write a unit test that instantiates `MinerUSettings` with `disable_maxtasksperchild=True` and verifies `maxtasksperchild` is `None`.

## Test Requirements
- Unit test: `MinerUSettings` can be instantiated with default values.
- Unit test: `MinerUSettings` correctly reads `MINERU_*` environment variables.
- Unit test: `MinerUSettings` Unknown extra fields are ignored (consistent with extra='ignore') and do not alter validated settings.
- Unit test: Removed fields (`paginate_output`, `processors`, `disable_multiprocessing`) are not accepted.
- Note: Testing `extract_mineru_settings_from_job_input()` integration with `MinerUSettings` is deferred to Task 05, since that function is implemented in Task 03.
