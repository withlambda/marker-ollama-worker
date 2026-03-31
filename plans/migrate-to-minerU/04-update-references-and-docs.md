# Task 04 — Update All References and Documentation

## Dependencies
- Task 02 (Refactor Settings)
- Task 03 (Refactor Python Handler)

## Requirements Traced
- FR-6 (Naming Consistency)
- NFR-4 (Test Coverage — `check_dependencies.py`)

## Implementation Steps

### 1. Update `check_dependencies.py`

- In the `modules_to_check` list, replace `"marker"` with `"mineru"`.
- Add `"paddle"` to the modules list to verify PaddlePaddle is installed.
- Remove any marker-specific sub-module checks if present.

### 2. Update `README.md`

This is the largest documentation change. Perform a systematic replacement:

**Title and Introduction**:
- `# NoteLM - Marker-PDF + vLLM` → `# NoteLM - MinerU + vLLM`
- Update the subtitle and project description to reference MinerU instead of marker-pdf.

**Architecture Section**:
- Replace "Marker Phase" with "MinerU Phase" throughout.
- Update the description of what happens during the conversion phase (visual layout analysis, PaddleOCR, etc.).
- Update process architecture descriptions (MinerU does not load Surya models).
- Update VRAM management section (MinerU models instead of "Marker models (Surya, etc.)").

**Features Section**:
- Update references from marker-pdf to MinerU.

**Model Management Section**:
- Replace the "Marker/Surya internal models" section with MinerU model management.
- Remove the `create_model_dict()` Python command.
- Document the `mineru.json` configuration and `MINERU_TOOLS_CONFIG_PATH`.
- Remove references to Surya model checkpoints (`DETECTOR_MODEL_CHECKPOINT`, etc.).

**Job Input Format**:
- Replace all `marker_*` keys with `mineru_*` keys in examples and tables.
- Remove keys that no longer apply (`marker_paginate_output`, `marker_processors`, `marker_disable_multiprocessing`).
- Update the Marker Configuration Overrides table → MinerU Configuration Overrides.

**Environment Variables Tables**:
- Replace all `MARKER_*` variables with `MINERU_*` equivalents.
- Remove variables that no longer apply.
- Update the "Surya / Marker Models" section to document MinerU model configuration.
- Update the Recommended Environment Variables table.

**Installation Section**:
- Update the `docker build` command name if needed.
- Update the pip resolver note (marker-pdf openai conflict may no longer apply).

**Local Testing Section**:
- Update any references to marker in test instructions.

**Troubleshooting Section**:
- Update VRAM troubleshooting to reference MinerU instead of Marker.
- Remove Surya-specific troubleshooting.

### 3. Update `test/marker.env` → `test/mineru.env`

- Rename the file from `marker.env` to `mineru.env`.
- Update all `MARKER_*` variable names to `MINERU_*`.
- Update `test/run.sh` if it references `marker.env`.
- Update related script comments/log labels so no stale marker-pdf naming remains.

### 3a. Update `test/custom.env`

- Rename `MARKER_DEBUG=true` → `MINERU_DEBUG=true`.
- Rename `MARKER_DISABLE_MAXTASKSPERCHILD=true` → `MINERU_DISABLE_MAXTASKSPERCHILD=true`.

### 3b. Update `test/tools.env`

- Update the comment referencing marker (line 16: *"Contains values for environment variables of tools that are used by marker"*) to reference MinerU.

### 4. Remove `test/surya.env`

- This file only contains Surya model checkpoint variables (`DETECTOR_MODEL_CHECKPOINT`, etc.) and a commented-out `MARKER_MODEL_NAME`. It has no MinerU equivalent.
- Delete the file entirely.
- Remove any references to `surya.env` in `test/run.sh` or other scripts.

### 5. Audit and Update `config/download-models/` (Directory-Wide)

This is the single consolidated audit point for the `config/download-models/` directory (not split across tasks).

- Replace `marker-models.txt` with `mineru-models.txt` listing the MinerU model repositories, or remove the list file entirely if models are handled only by `download_models_hf.py`.
- Replace all references to Marker/Surya models with MinerU models in `config/download-models/README.md`. Document the new model download process using `download_models_hf.py`.
- Update `download-models-from-hf.sh` to reference MinerU model repos and filenames.
- Update `exec-model-download.sh` so no hard-coded `marker-models.txt` or marker-specific comments remain.
- Verify `huggingface-hub.dockerfile` still copies the correct filenames and does not rely on removed marker-specific files.

### 6. Update Comments

- Update the comment on line 53 of the Dockerfile: `# --- Fix for Sequential GPU Workflows (Marker -> vLLM) ---` → `# --- Fix for Sequential GPU Workflows (MinerU -> vLLM) ---`.
- Update the comment on line 164 of `vllm_worker.py`: `# Critical if Marker used the GPU earlier` → `# Critical if MinerU used the GPU earlier`.
- Update any other Dockerfile comments that reference "Marker" (already partially covered by Task 01, but verify no comments were missed).

### 7. Final Sweep — Grep for Remaining "marker" References

Run a project-wide search for case-insensitive "marker" to catch any remaining references in:
- Source code comments
- Log messages
- Configuration files
- Shell scripts
- Documentation

**Important**: Also check `VllmSettings` docstrings in `settings.py` — the `vllm_vram_recovery_delay` field docstring currently says *"Seconds to wait after Marker before starting vLLM"* and must be updated. This lives inside `VllmSettings`, not `MarkerSettings`, so it may be missed by a class-scoped rename.

Exclude:
- `LICENSE` file
- Git history
- The `plans/` directory itself
- Any `begin_marker` / `end_marker` references in `LanguageProcessor` (these refer to description markers, not marker-pdf)

Preferred deterministic command:
```bash
rg -n -i "marker" \
  --glob "*.py" --glob "*.md" --glob "*.env" --glob "*.sh" --glob "*.txt" \
  --glob "!plans/**" --glob "!LICENSE"
```

Allowed false-positive tokens to manually ignore after the command:
- `begin_marker`
- `end_marker`

## Test Requirements
- `check_dependencies.py` must pass with `mineru` and `paddle` imports (inside Docker or with local install).
- The deterministic `rg` command above returns zero marker-pdf references after excluding approved false positives.
- `README.md` renders correctly with no broken links or references.
- All test env files (`mineru.env`, `custom.env`, `tools.env`) load without errors. `surya.env` has been removed.
- No files under `config/download-models/` should still reference `marker-models.txt` or stale marker-pdf model download behavior unless explicitly documented as intentional.

