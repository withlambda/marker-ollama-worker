# `handler.py`

## Context
This file serves as the main entry point for the RunPod Serverless worker. It processes input documents using `marker-pdf` and optionally enhances the output using a local Ollama LLM. It is designed to run inside the Docker container defined for this project.

## Interfaces

### Global Variables and Constants

*   `ALLOWED_INPUT_FILE_EXTENSIONS`: Set of supported extensions (`.pdf`, `.pptx`, `.docx`, `.xlsx`, `.html`, `.epub`).
*   `VALID_OUTPUT_FORMATS`: Supported output formats (`json`, `markdown`, `html`, `chunks`).
*   `VRAM_RESERVE_GB`: VRAM to reserve for overhead (Default: 4).
*   `OLLAMA_VRAM_PER_TOKEN_FACTOR`: GB per token (Default: 0.00013).
*   `OLLAMA_CONTEXT_LENGTH`: Context window length for LLM (Default: 4096).
*   `ARTIFACT_DICT`: Global cache for marker models.
*   `BLOCK_CORRECTION_PROMPT_LIBRARY`: Dictionary mapping prompt keys to actual prompt strings.

### Functions

#### `load_models()`
Loads marker models into memory (`ARTIFACT_DICT`) if not already loaded. If they are already loaded, it ensures they are moved to the GPU and clears the CUDA cache.

#### `unload_marker_models()`
Moves marker models from the GPU to the CPU and clears the CUDA cache. This is used to free VRAM for the Ollama model while keeping the marker models in memory for warm restarts.

#### `load_block_correction_prompts()`
Loads the prompt catalog from `block_correction_prompts.json` into `BLOCK_CORRECTION_PROMPT_LIBRARY`.

#### `calculate_optimal_workers(num_files: int, use_postprocess_llm: bool, marker_workers_override: Optional[int] = None) -> Tuple[int, int, int]`
Calculates optimal worker counts for Marker (`marker_workers`), Ollama thread count (`ollama_chunk_workers`), and Ollama parallelism (`ollama_num_parallel`) based on workload and available VRAM (`VRAM_GB_TOTAL`, `MARKER_VRAM_GB_PER_WORKER`, `OLLAMA_VRAM_GB_MODEL`, `OLLAMA_VRAM_FACTOR`, `OLLAMA_CONTEXT_LENGTH`).
1.  **Marker Workers**: Scaled based on `num_files` and VRAM availability (capped at 4).
2.  **Ollama Parallelism (`ollama_num_parallel`)**: Calculated using the context VRAM formula:
    `parallel = floor((TOTAL_VRAM - VRAM_RESERVE - OLLAMA_BASE_VRAM) / (OLLAMA_VRAM_FACTOR * OLLAMA_CONTEXT_LENGTH))`
3.  **Ollama Threads (`ollama_chunk_workers`)**: Set to a high fixed value (16) to saturate Ollama's internal request queue, maximizing GPU throughput.

#### `_save_marker_output(out_folder: Path, file_stem: str, full_text: str, out_meta: Dict[str, Any], images: Dict[str, Any], output_format: str) -> Path`
Saves the converted content (text, metadata, images) to the output folder.
1.  Determines the file extension based on `output_format`.
2.  Saves the extracted text to a file using `Path.write_text`.
3.  Saves metadata as a JSON file.
4.  Saves extracted images.
5.  Returns the path to the main output file.

#### `marker_process_single_file(file_path: Path, artifact_dict: Optional[Dict[str, Any]], marker_config: Dict[str, Any], output_base_path: str, output_format: str) -> Tuple[bool, Path]`
Processes a single file using a freshly initialized `marker` converter (for thread safety).
1.  Initializes `PdfConverter` with shared `artifact_dict` and task-specific `marker_config`.
2.  Converts file to text and images.
3.  Creates output subfolder named after the file.
4.  Calls `_save_marker_output` to save the results.
5.  Returns a success flag and the path to the generated output file.

#### `handler(job: Dict[str, Any]) -> Dict[str, str]`
Main RunPod entry point.
1.  **Configuration and Environment Setup**: Calls `setup_config()` once to perform environment validation and directory configuration using `GlobalConfig`.
2.  **Setup**: Logs initial VRAM state, loads marker models, and loads prompt catalog.
3.  **Input Parsing**:
    *   Reads job inputs (`input_dir`, `output_dir`, `output_format`, etc.).
    *   **Settings Extraction**: Uses `extract_ollama_settings_from_job_input` and `extract_marker_settings_from_job_input` to create structured `OllamaSettings` and `MarkerSettings` objects.
4.  **Ollama Initialization**: If enabled, starts Ollama server to verify or build the model using `ollama_settings`, then stops it and clears CUDA cache.
5.  **Marker Conversion**:
    *   Constructs absolute paths for input and output directories based on `GlobalConfig.volume_root_mount_path`.
    *   Prepares `marker_config` using `MarkerSettings`.
    *   Finds valid files in the input directory.
    *   Uses `ThreadPoolExecutor` and `as_completed` to process files in parallel, passing configuration to each task.
6.  **LLM Post-processing**:
    *   If enabled and `processed_files` is not empty:
        *   Moves Marker models to CPU to free VRAM.
        *   Starts Ollama server using `ollama_settings`.
        *   Iterates through `processed_files` sequentially.
        *   Calls `ollama_worker.process_file` with chunk parallelism.
        *   Stops Ollama server and clears CUDA cache after processing.
7.  **Cleanup**: Deletes ONLY the original input files for which processing was successful, if `delete_input_on_success` is enabled.
8.  **Return**: Returns a completion status message.

## Logic
*   **Worker Auto-scaling**: Dynamically balances marker parallelism vs Ollama chunk parallelism to avoid OOM while maximizing GPU utilization.
*   **Format Support**: Supports LLM post-processing for all valid output formats (`json`, `markdown`, `html`, `chunks`).
*   **Robust Cleanup**: Ensures input files are only removed on success, facilitating retries for failed files.
*   **Prompt Management**: Allows users to specify prompts by key (from a catalog) or directly in the job input.
*   **Execution Isolation**: Uses a dual-process architecture (supervisor and worker) via `multiprocessing` with the `spawn` start method for CUDA safety and better fault tolerance.

## Dependencies
*   `runpod`, `os`, `shutil`, `time`, `json`, `sys`, `torch`, `pathlib`, `concurrent.futures`
*   `marker` (converters, models, config, output)
*   `ollama_worker.OllamaWorker`
*   `utils.TextProcessor`, `utils` (path validation and VRAM logging helpers)
