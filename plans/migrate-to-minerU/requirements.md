# Requirements — Migrate from Marker-PDF to MinerU

## Functional Requirements

### FR-1: PDF-to-Markdown Conversion via MinerU
- The pipeline must use MinerU (`mineru`) instead of `marker-pdf` to convert PDF documents to Markdown.
- MinerU must correctly handle two-column layouts, preserving reading order within each column before merging.

### FR-2: Docker Image with Baked-In Models
- All MinerU model weights (layout analysis, OCR, formula recognition, table recognition) must be downloaded and embedded during the Docker image build phase.
- No runtime model downloads are permitted (RunPod Serverless has no persistent filesystem between cold starts).
- The `mineru.json` configuration file must be generated at build time and point to the baked-in model paths.
- The `MINERU_TOOLS_CONFIG_PATH` environment variable must be set to the path of the `mineru.json` file.

### FR-3: Multiprocessing Architecture Preserved
- The `multiprocessing.set_start_method('spawn')` architecture must be retained.
- The `mp.Pool` parallel processing pattern must be kept, with worker init/exit lifecycle.
- The VRAM-based calculation of optimal worker count must be preserved, but function and variable names must no longer reference "marker".

### FR-4: vLLM Post-Processing Pipeline Unchanged
- The sequential execution model (MinerU phase → vLLM phase) must be preserved.
- The `vllm_worker.py` server/client logic must remain unchanged.
- The vLLM post-processing (block correction, image descriptions) must receive the same Markdown + image output structure it currently expects.

### FR-5: Output Compatibility
- MinerU output must produce:
  - A Markdown `.md` file per input PDF (compatible with the current vLLM text chunking pipeline).
  - Extracted images saved alongside the Markdown file (matching the current `![alt](_page_X_Picture_Y.ext)` or equivalent tag format so `insert_image_descriptions_to_text_file` can locate them).
- The `_save_marker_output` function must be replaced or adapted to handle MinerU's output format (MinerU writes its own output files; the save logic may simplify).

### FR-6: Naming Consistency
- All code references to "marker" (variable names, function names, class names, docstrings, comments, log messages) must be renamed to reference "MinerU" as appropriate.
- The `MarkerSettings` Pydantic model must be renamed (e.g., `MinerUSettings`) with updated field names and environment variable prefixes.
- The `README.md` must be updated to reflect the new pipeline (MinerU + vLLM).

## Non-Functional Requirements

### NFR-1: VRAM Budget
- The pipeline must continue to operate within a 24 GB VRAM budget.
- MinerU models must fit within the same VRAM envelope previously used by Marker/Surya models (~5 GB per worker).

### NFR-2: Build Reproducibility
- The Dockerfile must pin MinerU and PaddlePaddle versions for reproducible builds.
- The model download script (`download_models_hf.py`) must be fetched from a pinned commit/tag of the MinerU repository.

Pinned baseline for this migration plan:
- Base image: `pytorch/pytorch:2.10.0-cuda12.6-cudnn9-runtime`
- `mineru[full]==3.0.1`
- `paddlepaddle-gpu==3.3.0` (installed from the CUDA 12.6 wheel index: `https://www.paddlepaddle.org.cn/packages/stable/cu126/`)
- `download_models_hf.py` source pinned to MinerU tag `v3.0.1`

### NFR-3: Updated Job Input API
- The RunPod job input JSON schema will be updated to use MinerU-specific keys.
- Field names change from `marker_*` to `mineru_*`.
- Semantics (workers, output_format, page_range, etc.) will map cleanly to the new engine.

### NFR-4: Test Coverage
- Tests must run with real installed required dependencies (`mineru` and `paddlepaddle-gpu`) and must not rely on dummy `sys.modules` shims for required third-party packages.
- Existing tests that currently reference `marker.*` must be refactored to use MinerU-compatible behavior-level patches/mocks after normal imports.
- The `check_dependencies.py` script must validate `mineru` instead of `marker`.

## Edge Cases & Pitfalls

### EC-1: PaddlePaddle GPU Compatibility
- **CRITICAL**: PaddlePaddle requires a CUDA-version-specific wheel (e.g., `paddlepaddle-gpu` for CUDA 12.x). The Dockerfile must select the correct wheel matching the base image CUDA version (CUDA 12.6, using the `cu126` wheel index).
- PaddlePaddle and PyTorch may conflict on CUDA shared libraries; validate both can coexist in the same image.

### EC-2: MinerU Output Structure Differences
- MinerU writes output to its own directory structure (separate `content_list.json`, images folder, `.md` file). The handler must adapt to read from MinerU's output layout rather than the `(full_text, out_meta, images)` tuple returned by Marker.
- MinerU image references in Markdown may use different path conventions than Marker. The image description insertion logic (`insert_image_descriptions_to_text_file`) regex patterns must be verified/adapted.

### EC-3: MinerU API Differences
- MinerU does not have a `create_model_dict()` → `PdfConverter` workflow. It uses a different API (e.g., `mineru.pipe.UNIPipe` or CLI-based invocation). The worker init/process functions must be rewritten accordingly.
- MinerU may not support all the same configuration options as Marker (e.g., `paginate_output`, `processors`, `disable_multiprocessing`). Unsupported options must be removed or mapped to MinerU equivalents.

### EC-4: Model Download During Build
- The MinerU `download_models_hf.py` script may require network access and Hugging Face authentication during build. The Dockerfile must handle this (e.g., `--build-arg HF_TOKEN`).
- Model sizes for MinerU may differ from Marker/Surya. Verify the Docker image size remains manageable.

### EC-5: Spawn-Safe MinerU Workers
- MinerU uses PaddlePaddle which has its own CUDA initialization. Verify that PaddlePaddle works correctly with `mp.set_start_method('spawn')` and that models can be loaded in child processes.

## Definition of Done

1. The Dockerfile builds successfully with MinerU + PaddlePaddle + vLLM, all models baked in, no runtime downloads.
2. `handler.py` uses MinerU API for PDF conversion with `mp.Pool` parallelism; no marker-pdf imports remain.
3. `settings.py` has a renamed `MinerUSettings` class with appropriate fields for MinerU configuration.
4. The vLLM post-processing phase (block correction + image descriptions) works unchanged on MinerU output.
5. All test files pass with updated MinerU references and behavior-level test patches.
6. `check_dependencies.py` validates `mineru` (not `marker`).
7. `README.md` fully reflects the MinerU-based pipeline.
8. No references to "marker" remain in source code, configuration, or documentation (except historical/license context and `begin_marker`/`end_marker` image description labels).
9. The pipeline processes a two-column PDF fixture and produces correct reading-order Markdown. A specific two-column PDF fixture must be identified or created and placed in the test directory (e.g., `test/fixtures/two-column-sample.pdf`) with known expected reading-order anchors.
10. A regression test verifies MinerU Markdown image paths are compatible with `list_extracted_images_for_output_file()` and `insert_image_descriptions_to_text_file()`.
