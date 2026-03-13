# `handler.py`

## Context
This file serves as the main entry point for the RunPod Serverless worker. It processes input documents using `marker-pdf` and optionally enhances the output using a local Ollama LLM. It is designed to run inside the Docker container defined for this project.

## Interfaces

### Global Variables and Constants

*   `ALLOWED_INPUT_FILE_EXTENSIONS`: Set of supported extensions (`.pdf`, `.pptx`, `.docx`, `.xlsx`, `.html`, `.epub`).
*   `VALID_OUTPUT_FORMATS`: Supported output formats (`json`, `markdown`, `html`, `chunks`).
*   `VRAM_RESERVE_GB`: VRAM to reserve for overhead (Default: 4).
*   `ARTIFACT_DICT`: Global cache for marker models.
*   `BLOCK_CORRECTION_PROMPT_LIBRARY`: Dictionary mapping prompt keys to actual prompt strings.

### Functions

#### `load_models()`
Loads marker models into memory (`ARTIFACT_DICT`) if not already loaded.

#### `load_block_correction_prompts()`
Loads the prompt catalog from `block_correction_prompts.json` into `BLOCK_CORRECTION_PROMPT_LIBRARY`.

#### `calculate_optimal_workers(num_files: int, use_postprocess_llm: bool, marker_workers_override: Optional[int] = None) -> Tuple[int, int]`
Calculates optimal worker counts for Marker (`marker_workers`) and Ollama (`ollama_chunk_workers`) based on workload and available VRAM (`TOTAL_VRAM_GB`, `MARKER_VRAM_PER_WORKER`, `OLLAMA_VRAM_PER_WORKER`).

#### `marker_process_single_file(file_path: Path, converter: PdfConverter, output_base_path: str, output_format: str) -> Tuple[bool, Path]`
Processes a single file using the `marker` converter.
1.  Converts file to text and images.
2.  Creates output subfolder named after the file.
3.  Saves output file (format-specific extension), metadata JSON, and extracted images.
4.  Returns a success flag and the path to the generated output file.

#### `handler(job: Dict[str, Any]) -> Dict[str, str]`
Main RunPod entry point.
1.  **Setup**: Initializes `TextProcessor`, loads marker models, and loads prompt catalog.
2.  **Configuration**: Resolves paths and environment variables (`VOLUME_ROOT_MOUNT_PATH`, `USE_POSTPROCESS_LLM`, etc.).
3.  **Input Parsing**: Reads job inputs (`input_dir`, `output_dir`, `output_format`, `marker_workers`, `ollama_chunk_workers`, `ollama_block_correction_prompt`, `block_correction_prompt_key`, `delete_input_on_success`).
4.  **Prompt Resolution**: Uses custom prompt or looks up by key in the catalog.
5.  **Path Resolution**: Constructs absolute paths using `VOLUME_ROOT_MOUNT_PATH` if relative.
6.  **Validation**: Validates directories and cleanup settings.
7.  **Marker Conversion**:
    *   Initializes `PdfConverter`.
    *   Finds valid files in the input directory.
    *   Uses `ThreadPoolExecutor` and `as_completed` to process files in parallel.
    *   Tracks `successful_inputs` and `processed_files`.
8.  **LLM Post-processing**:
    *   If enabled and `processed_files` is not empty:
        *   Starts Ollama server and ensures model exists.
        *   Iterates through `processed_files` sequentially.
        *   Calls `ollama_worker.process_file` with chunk parallelism.
        *   Stops Ollama server after processing.
9.  **Cleanup**: Deletes ONLY the original input files for which processing was successful, if `delete_input_on_success` is enabled.
10. **Return**: Returns a completion status message.

## Logic
*   **Worker Auto-scaling**: Dynamically balances marker parallelism vs Ollama chunk parallelism to avoid OOM while maximizing GPU utilization.
*   **Format Support**: Supports LLM post-processing for all valid output formats (`json`, `markdown`, `html`, `chunks`).
*   **Robust Cleanup**: Ensures input files are only removed on success, facilitating retries for failed files.
*   **Prompt Management**: Allows users to specify prompts by key (from a catalog) or directly in the job input.

## Dependencies
*   `runpod`, `os`, `shutil`, `time`, `json`, `sys`, `pathlib`, `concurrent.futures`
*   `marker` (converters, models, config, output)
*   `ollama_worker.OllamaWorker`
*   `utils.TextProcessor`, `utils` (path validation helpers)
