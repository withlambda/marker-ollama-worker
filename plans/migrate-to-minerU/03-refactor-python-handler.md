# Task 03 — Refactor Python Handler

## Dependencies
- Task 01 (Dockerfile Overhaul) — MinerU must be installable for import verification.
- Task 02 (Refactor Settings) — `MinerUSettings` and `MINERU_*` field mapping must be available before wiring handler logic.

## Requirements Traced
- FR-1 (PDF-to-Markdown Conversion via MinerU)
- FR-3 (Multiprocessing Architecture Preserved)
- FR-5 (Output Compatibility)
- FR-6 (Naming Consistency)
- EC-2 (MinerU Output Structure Differences)
- EC-3 (MinerU API Differences)
- EC-5 (Spawn-Safe MinerU Workers)

## Implementation Steps

### 0. Verify MinerU API Surface (Pre-Implementation Spike)

To avoid repeated multi-GB downloads, perform this verification inside the `notelm-mineru-test` image created in Task 01:

1. **Start the test container in interactive mode or with a script**:
   ```bash
   docker run --rm -it notelm-mineru-test python3
   ```
2. **Confirm the exact API of `mineru[full]==3.0.1`** by running a minimal test script or inspecting its source inside the container.
3. **Verify that the following imports and method calls exist** and behave as documented in `design.md`:
  ```python
from mineru.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from mineru.data.dataset import PymuDocDataset
from mineru.model.doc_analyze_by_custom_model import doc_analyze
  ```
- If the API differs from `design.md`, update `design.md` before proceeding.
- Document the verified API (method signatures, return types) in this task file or in `design.md`.
- Run one real end-to-end spike on a sample PDF before broader handler refactoring begins. Record:
  - the exact wrapper code path used to convert the PDF,
  - whether MinerU requires any process-local bootstrap/warm-up,
  - the location and names of generated Markdown/images/metadata artifacts,
  - the Markdown image-link syntax emitted by MinerU.
- Do **not** proceed to the full handler rename/refactor until one PDF converts successfully with the verified API.

### 1. Replace Marker Imports and Bootstrap a Minimal MinerU Conversion Wrapper

Remove:
```python
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser
from marker.output import text_from_rendered
```

Add MinerU equivalents (update if spike reveals different imports):
```python
from mineru.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from mineru.data.dataset import PymuDocDataset
from mineru.model.doc_analyze_by_custom_model import doc_analyze
```

- Introduce the smallest possible wrapper around the verified MinerU API that can convert a single PDF into an output directory.
- Keep this wrapper isolated until the spike proves the input/output contract.

### 2. Rewrite Worker Init/Exit

**`marker_worker_init()` → `mineru_worker_init()`**:
- MinerU does not require a pre-loaded global model dictionary like Marker's `create_model_dict()`.
- Models are loaded on-demand based on the `mineru.json` configuration.
- The worker init function should verify that the MinerU config path is accessible and optionally perform a warm-up call to ensure models are cached in GPU memory.
- Keep the `atexit.register(mineru_worker_exit)` pattern.

**`marker_worker_exit()` → `mineru_worker_exit()`**:
- Clear any PaddlePaddle GPU state (`paddle.device.cuda.empty_cache()` if available).
- Keep the existing `torch.cuda.empty_cache()` and `gc.collect()` cleanup.
- Remove references to `_MARKER_MODELS` global variable.

**Global variable**:
- Remove `_MARKER_MODELS: Optional[Dict[str, Any]] = None`.
- If MinerU requires any process-local state, add an equivalent (e.g., `_MINERU_INITIALIZED: bool = False`).

### 3. Rewrite `marker_process_single_file()` → `mineru_process_single_file()`

The new function must:
1. Read the PDF file as bytes.
2. Create a `PymuDocDataset` from the bytes.
3. Run layout analysis and OCR via MinerU's pipeline API.
4. Write output (Markdown + images) to the output directory.
5. Return `(True, output_file_path)` on success or `(False, None)` on failure.

Key differences from Marker:
- MinerU writes images directly to disk during processing (no `images` dict to save manually).
- MinerU produces a `.md` file as direct output; no `text_from_rendered()` post-processing needed.
- The output directory structure may differ (MinerU may create an `images/` subfolder). Ensure the `.md` file uses relative paths to images that `list_extracted_images_for_output_file()` and `insert_image_descriptions_to_text_file()` can find.

Signature:
```python
def mineru_process_single_file(
    app_config: GlobalConfig,
    file_path: Path,
    mineru_config: Dict[str, Any],
    output_base_path: Path,
    output_format: str
) -> Tuple[bool, Optional[Path]]:
```

### 4. Normalize the Verified MinerU Output Contract for Downstream Use

- Based on the Step 0 spike, choose a single canonical contract for downstream processing:
  - Option A: keep MinerU's native output layout and adapt helpers/tests to it.
  - Option B: normalize MinerU output into the existing `output/<stem>/` layout during `mineru_process_single_file()`.
- Document the chosen contract in `design.md` once verified.
- Ensure the handler returns or records the canonical Markdown path deterministically.
- Ensure image discovery works with the chosen contract before moving on to broad naming cleanup.

### 5. Adapt or Remove `_save_marker_output()`

- MinerU writes its own output files, so the explicit save logic (`_save_marker_output`) may no longer be needed.
- If MinerU's output location does not match the expected structure, add a post-processing step to move/rename files into the `output/<stem>/` directory structure.
- Keep metadata saving if MinerU provides equivalent metadata (e.g., page count, OCR confidence).

### 6. Rename `calculate_optimal_marker_workers()` → `calculate_optimal_mineru_workers()`

- Update the function name, parameter name (`marker_config` → `mineru_config`), type hint (`MarkerSettings` → `MinerUSettings`), docstring, and log messages.
- The VRAM calculation logic remains the same (it is engine-agnostic).

### 7. Rename `extract_marker_settings_from_job_input()` → `extract_mineru_settings_from_job_input()`

- Change the prefix filter from `"marker_"` to `"mineru_"`.
- Update the `MarkerSettings` reference to `MinerUSettings`.
- Update the valid fields set and warning messages.

### 8. Update `handler()` Function

- Replace all references to `marker_settings`, `marker_config`, `optimal_marker_workers` with `mineru_settings`, `mineru_config`, `optimal_mineru_workers`.
- Update the `marker_config` dict (lines 551-562) to pass MinerU-relevant options only (remove `paginate_output`, `processors`, `disable_multiprocessing`, `use_llm`; add MinerU-specific options like `ocr` mode).
- Update `mp.Pool` call to use `mineru_worker_init` as the initializer.
- Update `pool.starmap` to call `mineru_process_single_file`.
- Update all log messages from "Marker" to "MinerU".
- Update the module docstring at the top of the file.

### 9. Review Worker / Process Compatibility Explicitly

- Confirm the verified MinerU workflow is spawn-safe under `torch.multiprocessing` / `mp.Pool` with the existing `spawn` start method.
- Decide whether any warm-up call belongs in `mineru_worker_init()` or whether on-demand initialization is safer.
- Verify cleanup responsibilities between Torch and Paddle so GPU memory is released between the MinerU and vLLM phases.
- If the spike reveals that MinerU is not safe to initialize in pooled workers, document the constraint and adjust the design/task plan before proceeding.

### 10. Verify Image Path Compatibility (Dedicated Sub-Task)

This is a **critical integration point** — a mismatch here silently breaks the vLLM post-processing pipeline.

**Step 10a — Document MinerU’s actual image output pattern**:
- Run MinerU on a sample PDF and record:
  - Where images are saved (flat alongside `.md` or in an `images/` subfolder).
  - The naming convention (e.g., `img_0.png`, `image_1.jpg`, etc.).
  - The Markdown image tag format (e.g., `![](images/img_0.png)`).

**Step 10b — Decide and implement adaptation strategy**:
- If MinerU places images in an `images/` subfolder:
  - Option A: Adapt `list_extracted_images_for_output_file()` to search recursively.
  - Option B: Move images to the flat structure during `mineru_process_single_file()`.
- Choose one option and implement it.

**Step 10c — Verify regex compatibility**:
- Confirm that `insert_image_descriptions_to_text_file()` regex patterns match MinerU’s image tag format.
- If they differ, update the regex patterns.

**Step 10d — Write contract regression test**:
- Write a test that creates a mock MinerU-style output directory (with the verified naming pattern) and asserts that:
  - `list_extracted_images_for_output_file()` finds all images.
  - `insert_image_descriptions_to_text_file()` correctly inserts descriptions into the Markdown.

**Acceptance criteria**: Both helper functions work correctly with MinerU’s actual output format, verified by an automated test, and the chosen canonical output contract is documented in `design.md`.

## Test Requirements
- Pre-refactor proof: one real sample PDF converts end-to-end with the verified MinerU API and produces a documented output contract.
- Unit test: `mineru_process_single_file()` produces a `.md` file and images in the expected directory structure (with real dependencies installed; use behavior-level patches only where needed).
- Unit test: `calculate_optimal_mineru_workers()` returns correct values for various VRAM/file-count combinations (reuse existing test logic with renamed function).
- Unit test: `extract_mineru_settings_from_job_input()` correctly parses `mineru_*` prefixed keys.
- Integration test: The full `handler()` flow processes a PDF through MinerU and produces output compatible with vLLM post-processing. Use the `notelm-mineru-test` image from Task 01 with a mounted volume and a shell script to run the test and record results.
- Integration regression: run a fixed two-column PDF fixture and assert expected reading-order anchors in produced Markdown.
- Contract regression: validate that MinerU-style Markdown image links are discoverable by `list_extracted_images_for_output_file()` and correctly consumed by `insert_image_descriptions_to_text_file()`.
