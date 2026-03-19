# Context
This file, `handler.py`, is the main entry point for the RunPod serverless worker. It orchestrates the entire document conversion workflow: environment initialization, VRAM-aware worker allocation, parallel document conversion using the `marker-pdf` library, and optional LLM post-processing (OCR correction and image descriptions) using a `vLLM` server.

# Interface

## Main Functions

### `handler(job: Dict[str, Any]) -> Dict[str, Any]`
The primary RunPod entry point.
- **Input**: A RunPod job dictionary with an `input` key containing:
  - `input_dir` (str): Path to documents (relative to volume root or absolute).
  - `output_dir` (str): Path to save results.
  - `output_format` (str, default: "markdown").
  - `marker_*`: Overrides for MarkerSettings.
  - `vllm_*`: Overrides for VllmSettings.
  - `delete_input_on_success` (bool, default: False).
- **Output**: Result summary with `status` ('completed', 'partially_completed', or 'success') and `failures` list.

### Helper Functions
- `calculate_optimal_marker_workers(num_files, app_config, marker_config) -> int`: Computes worker count based on `VRAM_GB_TOTAL`, `vram_gb_reserve`, and `marker_vram_gb_per_worker`. Max 4.
- `marker_worker_init()`: Loads marker models once per worker process into VRAM.
- `marker_process_single_file(...)`: Converts one file, saves text/images/meta, and handles errors.
- `insert_image_descriptions_to_text_file(...)`: Regex-based insertion of vision-model descriptions into Markdown.
- `extract_*_settings_from_job_input(...)`: Pydantic-based extraction and validation of settings from raw JSON input.

# Logic

### 1. Environment and Path Setup
- Configures environment variables for PyTorch, OpenMP, and CUDA (e.g., `mp.set_start_method("spawn")`).
- Validates that `input_dir` exists and contains supported files (`.pdf`, `.docx`, etc.).
- Prepares `output_dir` (optionally purges it if `CLEANUP_OUTPUT_DIR_BEFORE_START` is True).

### 2. Marker Conversion (Phase 1 - VRAM Heavy)
- Calculates optimal worker count.
- Uses `torch.multiprocessing.Pool` with `marker_worker_init` to load models in parallel.
- Executes `marker_process_single_file` for each input.
- Successful outputs are stored in `processed_files`.
- VRAM is freed when the Pool closes (workers terminate).

### 3. vLLM Post-processing (Phase 2 - VRAM Heavy)
- Starts the `VllmWorker` context manager (which spawns the vLLM server).
- **OCR Correction**: For each processed file, splits text into chunks and sends to vLLM concurrently. Overwrites file with corrected text.
- **Image Description**: Scans output directory for images. Sends images to vLLM vision model.
- **Insertion**: Uses regex `!\[.*?\]\((?:.*?[/\\])?{escaped_filename}(?:\?.*?)?\)` to find image tags in Markdown and inserts blockquotes with descriptions immediately after. If tags are missing, it appends a fallback section.
- Tracks `failed_post_processing` files.

### 4. Cleanup and Response
- Deletes original input files if `delete_input_on_success` is True and processing reached completion.
- Returns `completed` if all files succeeded, or `partially_completed` if some post-processing steps failed.

# Exceptions
- Explicitly disables Marker's internal LLM logic (`use_llm: False`) to avoid VRAM contention.
- Uses `atexit` and `torch.cuda.empty_cache()` to ensure resource cleanup.

# Goal
The prompt file provides the orchestration logic, VRAM management strategy, and error-handling patterns required to regenerate `handler.py` exactly, ensuring it correctly coordinates between Marker and vLLM.
