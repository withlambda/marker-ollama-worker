# Design — Migrate from Marker-PDF to MinerU

## Task Execution Order

Tasks are numbered for reference but must be executed in the following order due to dependencies:

```
Task 01 (Dockerfile Overhaul)
  └─→ Task 02 (Refactor Settings)
        └─→ Task 03 (Refactor Python Handler)
              └─→ Task 04 (Update References and Docs)
                    └─→ Task 05 (Update Tests)
```

Task 02 (Settings) must complete before Task 03 (Handler) because the handler depends on `MinerUSettings`.

## Local Development Strategy

The Dockerfile build (Task 01) may take time to stabilize. Tasks 02–05 can be developed and tested locally in parallel by installing `mineru[full]` and `paddlepaddle-gpu` in a virtual environment. 

**Note on Redundant Downloads**: These dependencies are several GB. To avoid repeated downloads:
1. Prefer running tasks inside the `markllm-mineru-test` Docker image built in Task 01.
2. If working locally, use a persistent virtual environment.
3. Check if dependencies are already installed before running `pip install`.

```bash
python -m venv .venv && source .venv/bin/activate
# Check before install
if ! python3 -c "import mineru; import paddle" 2>/dev/null; then
  pip install -r requirements.txt  # after requirements.txt is updated
fi
```

This allows code refactoring, settings changes, and test updates to proceed without a working Docker image.

## Mandatory Proof Gates

The migration should not proceed as a pure rename exercise. Two proof gates must be completed and documented before the broader refactor is considered in-flight:

1. **Task 01 compatibility proof**
   - Record successful import/version checks for `mineru`, `paddle`, and `vllm` on the chosen compatibility baseline.
   - Verify the actual CLI or invocation contract of MinerU's `download_models_hf.py` before the Dockerfile is rewritten around assumed flags.
2. **Task 03 end-to-end single-PDF proof**
   - Convert one real sample PDF with the verified MinerU API before renaming the rest of the handler.
   - Capture the actual output artifact contract (Markdown path, image layout, metadata files, Markdown image syntax) and use that as the basis for downstream helper changes.

## High-Level Architecture / Data Flow

The overall two-phase architecture remains identical; only the first phase changes its internal engine:

```
┌─────────────────────────────────────────────────────────────────────┐
│  RunPod Serverless Job                                              │
│                                                                     │
│  1. MinerU Phase (mp.Pool, spawn)                                   │
│     ┌──────────┐  ┌──────────┐  ┌──────────┐                       │
│     │ Worker 1 │  │ Worker 2 │  │ Worker N │   (parallel)           │
│     │ mineru   │  │ mineru   │  │ mineru   │                        │
│     └────┬─────┘  └────┬─────┘  └────┬─────┘                       │
│          │              │              │                             │
│          ▼              ▼              ▼                             │
│     output/<stem>/   output/<stem>/  output/<stem>/                 │
│       ├─ <stem>.md   ├─ <stem>.md   ├─ <stem>.md                   │
│       ├─ images/ ?   ├─ images/ ?   ├─ images/ ?                   │
│       └─ metadata ?  └─ metadata ?  └─ metadata ?                  │
│                                                                     │
│  ── CUDA cache cleared, VRAM released ──                            │
│                                                                     │
│  2. vLLM Phase (subprocess, unchanged)                              │
│     ├─ Block correction (text chunking → LLM → reassembly)         │
│     ├─ Image descriptions (vision LLM)                              │
│     └─ Insert descriptions into .md files                           │
│                                                                     │
│  3. Cleanup & Return result                                         │
└─────────────────────────────────────────────────────────────────────┘
```

> `images/` and metadata file names are provisional placeholders above. Task 03 must replace assumptions with the verified MinerU output contract before downstream helper logic is finalized.

### Key Change: MinerU API Integration

**Marker (current)**:
```python
from marker.models import create_model_dict
from marker.converters.pdf import PdfConverter
from marker.config.parser import ConfigParser
from marker.output import text_from_rendered

models = create_model_dict()            # worker init
config_parser = ConfigParser(config)
converter = PdfConverter(config=..., artifact_dict=models, ...)
rendered = converter(str(file_path))
full_text, out_meta, images = text_from_rendered(rendered)
```

**MinerU (target)**:

> **⚠️ API not yet verified**: The code below is based on MinerU documentation and examples but has not been confirmed against `mineru[full]==3.0.1`. Task 03, Step 0 requires verifying the exact API surface before implementation. Update this section with the verified API.

```python
from mineru.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from mineru.data.dataset import PymuDocDataset
from mineru.model.doc_analyze_by_custom_model import doc_analyze

# worker init: no global model dict needed (MinerU loads models on demand
# or via environment config pointing to baked-in weights)

# per-file processing:
reader = FileBasedDataReader("")
writer = FileBasedDataWriter(output_dir)
pdf_bytes = reader.read(str(file_path))
dataset = PymuDocDataset(pdf_bytes)
infer_result = dataset.apply(doc_analyze, ocr=True)
pipe_result = infer_result.pipe_ocr_mode(writer, writer)
md_content = pipe_result.get_markdown(writer)
```

The exact MinerU output layout must be verified from a real spike run before the handler is finalized. The downstream vLLM phase depends on the verified Markdown file path, image storage layout, and image-reference syntax.

## Required MinerU Output Contract (To Be Verified in Task 03)

Task 03 must confirm and document the real values for the following output-contract fields before helper or handler refactoring is considered complete:

| Contract Element | Expected Questions to Answer |
|:-----------------|:-----------------------------|
| Primary Markdown artifact | What file is the canonical converted text output and where is it written? |
| Image storage layout | Are images flat beside the Markdown file, nested in an `images/` subdirectory, or stored elsewhere? |
| Markdown image syntax | What exact relative paths / tag format does MinerU emit into Markdown? |
| Metadata artifacts | Does MinerU emit metadata JSON or sidecar files that must be preserved or normalized? |
| Naming determinism | Are filenames stable enough for downstream helper logic and regression tests? |

If MinerU's actual layout differs from the existing handler assumptions, Task 03 must either normalize the output into the current `output/<stem>/` contract or update the helper functions and tests to use the verified MinerU-native layout.

## Abort Conditions

The migration must be paused and reassessed if any of the following occur during the proof gates:

1. **PaddlePaddle + vLLM coexistence failure**: If `paddlepaddle-gpu` and `vllm` cannot both be imported in the same Docker image due to conflicting CUDA shared library requirements, escalate before proceeding to Task 02.
2. **Base image unavailability**: If `pytorch/pytorch:2.10.0-cuda12.6-cudnn9-runtime` does not exist and no compatible fallback is found within the pinned dependency set, stop and re-evaluate the CUDA version strategy.
3. **MinerU API fundamentally incompatible**: If the Task 03 spike reveals that MinerU cannot be safely initialized inside `mp.Pool` spawn workers (e.g., PaddlePaddle hard-forks on CUDA init), the multiprocessing architecture must be redesigned before continuing.
4. **Model download script contract broken**: If `download_models_hf.py` from tag `v3.0.1` does not support offline model baking (e.g., requires runtime auth or network access after build), an alternative model-download strategy must be designed.

In all cases, document the blocker in the relevant task file and notify the user before attempting workarounds.

## Behavioral Compatibility Deltas

### Must remain compatible

- The service still accepts document jobs, produces Markdown output, and runs the existing vLLM post-processing phase afterward.
- The multiprocessing architecture remains spawn-safe and bounded by VRAM-aware worker sizing.
- Image-description helpers continue to discover extracted images and insert descriptions into the converted Markdown deterministically.

### Allowed to change if documented and tested

- OCR/model internals and model-loading behavior.
- Exact Markdown formatting details if MinerU's renderer differs, provided downstream processing and regression anchors remain valid.
- On-disk intermediate layout, but only if the verified contract is documented and helper/test updates preserve functional behavior.

## List of New/Modified Files

| File | Action | Description |
|:-----|:-------|:------------|
| `Dockerfile` | **Modify** | Replace marker-pdf install with `mineru[full]` + `paddlepaddle-gpu`. Add model download via `download_models_hf.py`. Generate `mineru.json`. Set `MINERU_TOOLS_CONFIG_PATH`. Remove marker font download and model baking. |
| `requirements.txt` | **Modify** | Replace `marker-pdf==1.10.2` with `mineru[full]==3.0.1`. Add `paddlepaddle-gpu==3.3.0` (installed from Paddle CUDA index). Remove marker-specific transitive dependencies if no longer needed. |
| `handler.py` | **Modify** | Replace all marker imports with MinerU equivalents. Rewrite `marker_worker_init` → `mineru_worker_init`, `marker_worker_exit` → `mineru_worker_exit`, `marker_process_single_file` → `mineru_process_single_file`, `_save_marker_output` → adapt or remove (MinerU self-writes). Rename `calculate_optimal_marker_workers` → `calculate_optimal_mineru_workers`. Update `extract_marker_settings_from_job_input` → `extract_mineru_settings_from_job_input`. Update all log messages, docstrings, and comments. |
| `settings.py` | **Modify** | Rename `MarkerSettings` → `MinerUSettings`. Update field names (`MARKER_*` env prefix → `MINERU_*`). Remove marker-only fields (e.g., `processors`, `paginate_output`) that have no MinerU equivalent. Add MinerU-specific fields if needed (e.g., `ocr_mode`). Update module docstring. |
| `check_dependencies.py` | **Modify** | Replace `"marker"` with `"mineru"` in modules list. Add `"paddle"` to the check list. |
| `config/download-models/marker-models.txt` | **Remove/Replace** | Remove marker model list. Optionally replace with a `mineru-models.txt` or remove entirely if models are baked via the `download_models_hf.py` script. |
| `config/download-models/README.md` | **Modify** | Update documentation to reference MinerU models instead of Marker/Surya models. |
| `config/download-models/download-models-from-hf.sh` | **Modify** | Update to download MinerU model repos instead of Marker/Surya repos. |
| `config/download-models/exec-model-download.sh` | **Modify** | Remove hard-coded marker model-list assumptions and keep helper script arguments aligned with the chosen MinerU model-download flow. |
| `config/download-models/huggingface-hub.dockerfile` | **Verify/Modify** | Verify that any copied filenames, wildcard assumptions, and container entrypoints still match the renamed model-list files and updated scripts. |
| `README.md` | **Modify** | Full rewrite of marker references → MinerU. Update architecture section, environment variables tables, job input examples, model management section, and troubleshooting. |
| `test/test-handler.py` | **Modify** | Update `marker_*` job input keys to `mineru_*`. |
| `test/test_handler_language_inference.py` | **Modify** | Remove marker module shims; use real imports with behavior-level patches for MinerU call sites. |
| `test/test_handler_image_description_helpers.py` | **Modify** | Remove PDF-engine import shims/dummy converter classes; keep helper tests engine-agnostic via normal imports. |
| `test/test_handler_end_to_end_language.py` | **Modify** | Remove marker module shims; update to MinerU naming and behavior-level patches only. |
| `test/test_vllm_worker_language_aware.py` | **Modify** | Remove marker module shims and keep only behavior-level patches where needed. |
| `test/marker.env` | **Rename/Modify** | Rename to `mineru.env` and update variable names from `MARKER_*` → `MINERU_*`. |
| `test/custom.env` | **Modify** | Rename `MARKER_DEBUG` → `MINERU_DEBUG`, `MARKER_DISABLE_MAXTASKSPERCHILD` → `MINERU_DISABLE_MAXTASKSPERCHILD`. |
| `test/tools.env` | **Modify** | Update comment referencing marker to reference MinerU. |
| `test/run.sh` | **Modify** | Update `marker.env` source to `mineru.env`, rename Docker container `marker-with-vllm-test` → `mineru-with-vllm-test`, update comments. |
| `test/test_vllm_worker_chunking.py` | **Verify** | Confirm no marker-pdf references; no changes expected. |
| `test/test_vllm_worker_event_loop.py` | **Verify** | Confirm no marker-pdf references; no changes expected. |
| `test/test_vllm_worker_token_budget.py` | **Verify** | Confirm no marker-pdf references; no changes expected. |
| `vllm_worker.py` | **No change** | Kept as-is per requirements. |
| `utils.py` | **No change** | No marker references; kept as-is. |

## API / Schema / Dependency Changes

### Python Dependencies

| Old | New |
|:----|:----|
| `marker-pdf==1.10.2` | `mineru[full]==3.0.1` |
| _(implicit via marker)_ Surya models | `paddlepaddle-gpu==3.3.0` (from `https://www.paddlepaddle.org.cn/packages/stable/cu126/`) |
| `vllm` (existing) | `vllm==0.18.0` (pin explicitly; verify CUDA 12.6 compatibility in Task 01 Step 0) |

### Build Reproducibility Pins

- Base image: `pytorch/pytorch:2.10.0-cuda12.6-cudnn9-runtime`
- `vllm==0.18.0`
- MinerU model downloader source: `https://raw.githubusercontent.com/opendatalab/MinerU/v3.0.1/scripts/download_models_hf.py`

### System Dependencies (Dockerfile)

| Old | New |
|:----|:----|
| `poppler-utils`, `tesseract-ocr` | `libgl1`, `libglib2.0-0` (OpenCV runtime deps for MinerU). `poppler-utils` may still be needed for `pdfinfo`. `tesseract-ocr` can likely be removed (MinerU uses PaddleOCR). |

### Environment Variable Prefix Changes

| Old Prefix | New Prefix |
|:-----------|:-----------|
| `MARKER_*` | `MINERU_*` |

Key renamed variables:
- `MARKER_WORKERS` → `MINERU_WORKERS`
- `MARKER_FORCE_OCR` → removed (replaced by `MINERU_OCR_MODE` with values `"ocr"`, `"txt"`, `"auto"`)
- `MARKER_VRAM_GB_PER_WORKER` → `MINERU_VRAM_GB_PER_WORKER`
- `MARKER_MAXTASKSPERCHILD` → `MINERU_MAXTASKSPERCHILD`
- `MARKER_OUTPUT_FORMAT` → `MINERU_OUTPUT_FORMAT`
- `MARKER_DEBUG` → `MINERU_DEBUG`

Removed (no MinerU equivalent):
- `MARKER_PAGINATE_OUTPUT`
- `MARKER_PROCESSORS`
- `MARKER_DISABLE_MULTIPROCESSING`

New:
- `MINERU_TOOLS_CONFIG_PATH` — path to `mineru.json` (set in Dockerfile)
- `MINERU_OCR_MODE` — OCR mode selection (`"ocr"`, `"txt"`, `"auto"`; default: `"auto"`)

### Job Input API Changes

| Old Key | New Key | Notes |
|:--------|:--------|:------|
| `marker_workers` | `mineru_workers` | Same semantics |
| `marker_force_ocr` | `mineru_ocr_mode` | Replaced by `ocr_mode` field (`"ocr"`, `"txt"`, `"auto"`); `force_ocr` boolean removed |
| `marker_disable_image_extraction` | `mineru_disable_image_extraction` | Same semantics |
| `marker_page_range` | `mineru_page_range` | Same semantics |
| `marker_output_format` | `mineru_output_format` | Kept as no-op for API compatibility; validated to accept only `"markdown"` |
| `marker_paginate_output` | — | No MinerU equivalent; remove |
| `marker_processors` | — | No MinerU equivalent; remove |
| `marker_disable_multiprocessing` | — | No MinerU equivalent; remove |
| `marker_maxtasksperchild` | `mineru_maxtasksperchild` | Same semantics |
| `marker_disable_maxtasksperchild` | `mineru_disable_maxtasksperchild` | Same semantics |

### MinerU Configuration File (`mineru.json`)

Generated at Docker build time and placed at a known path (e.g., `/app/mineru.json`):

```json
{
  "models-dir": "/app/models/mineru",
  "table-config": {
    "is_table_recog_enable": true,
    "max_time": 400
  },
  "layout-config": {
    "model": "doclayout_yolo"
  },
  "formula-config": {
    "mfd_model": "yolo_v8_mfd",
    "mfr_model": "unimernet_small",
    "enable": true
  }
}
```

The exact structure will be determined by the MinerU version used. The `MINERU_TOOLS_CONFIG_PATH` environment variable will point to this file.
