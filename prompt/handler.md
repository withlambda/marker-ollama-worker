# `handler.py`

## Context
This file serves as the main entry point for the RunPod Serverless worker. It processes input documents using `marker-pdf` and optionally enhances the output using a local Ollama LLM. It is designed to run inside the Docker container defined for this project.

## Interfaces

### Functions

#### `load_models()`
Loads marker models into memory (VRAM) if not already loaded (Warm Start). It uses the global `ARTIFACT_DICT`.

```python
def load_models() -> None:
```

#### `calculate_optimal_workers(num_files: int, use_postprocess_llm: bool, marker_workers_override: Optional[int] = None) -> Tuple[int, int]`
Calculates optimal worker counts for Marker and Ollama based on available VRAM and the number of files to process.

```python
def calculate_optimal_workers(
    num_files: int,
    use_postprocess_llm: bool,
    marker_workers_override: Optional[int] = None
) -> Tuple[int, int]:
```
*   **Args**:
    *   `num_files` (int): Number of files to process.
    *   `use_postprocess_llm` (bool): Whether LLM post-processing will be used.
    *   `marker_workers_override` (Optional[int]): Manual override for marker workers.
*   **Returns**: `Tuple[int, int]` - (marker_workers, ollama_chunk_workers).

#### `process_single_file(file_path: Path, converter: PdfConverter, output_base_path: str) -> Tuple[bool, Path]`
Processes a single file using the provided `marker` converter and saves the output (Markdown, JSON metadata, images) to a subfolder in the output directory.

```python
def process_single_file(
    file_path: Path,
    converter: PdfConverter,
    output_base_path: str
) -> Tuple[bool, Path]:
```

#### `handler(job: Dict[str, Any]) -> Dict[str, str]`
The main RunPod handler function.

```python
def handler(job: Dict[str, Any]) -> Dict[str, str]:
```
*   **Args**: `job` (Dict[str, Any]) - The job payload containing `input` configuration.
*   **Returns**: `Dict[str, str]` - Status and message.
*   **Environment Variables Used**:
    *   `VOLUME_ROOT_MOUNT_PATH` (Required): Base path for storage.
    *   `USE_POSTPROCESS_LLM` (Optional): Boolean to enable LLM.
    *   `CLEANUP_OUTPUT_DIR_BEFORE_START` (Optional): Boolean to clean output dir.
    *   `OLLAMA_MODEL` (Optional/Required): Model name for Ollama.
    *   `MARKER_DEBUG` (Optional): Boolean for debug mode.

## Logic
1.  **Initialization**:
    *   Initializes `TextProcessor`.
    *   Loads marker models into global `ARTIFACT_DICT` if not present.
    *   Reads configuration from `job['input']` and environment variables.
2.  **Validation**:
    *   Validates `input_dir` and `output_dir` paths.
    *   Checks if `input_dir` is a flat directory (no subdirectories) and contains valid file extensions.
    *   Checks `output_dir` state (empty or cleanup required).
3.  **Configuration**:
    *   Constructs `marker_config` dictionary based on job inputs and defaults.
    *   If `USE_POSTPROCESS_LLM` is true, configures Ollama service settings and pulls the model if necessary.
4.  **Converter Setup**:
    *   Instantiates `ConfigParser` and `PdfConverter` with the configuration and loaded models.
5.  **Processing**:
    *   Identifies valid files in `input_dir`.
    *   Uses `ThreadPoolExecutor` to process files in parallel based on `marker_workers`.
    *   Calls `process_single_file` for each file.
6.  **LLM Post-processing**:
    *   If enabled, starts the Ollama server and ensures the model is available.
    *   Processes each markdown file sequentially with `ollama_worker.process_file`.
7.  **Cleanup**:
    *   Unloads the model and stops the Ollama server.
    *   Deletes processed input files to save space/indicate completion.
8.  **Return**:
    *   Returns a success message with the status `completed`.

## Dependencies
*   `runpod`
*   `os`, `subprocess`, `requests`, `json`, `time`, `shutil`
*   `pathlib.Path`
*   `concurrent.futures.ThreadPoolExecutor`
*   `marker.converters.pdf.PdfConverter`
*   `marker.models.create_model_dict`
*   `marker.config.parser.ConfigParser`
*   `marker.output.text_from_rendered`

## Constants
*   `ALLOWED_INPUT_FILE_EXTENSIONS`: `{'.pdf', '.pptx', '.docx', '.xlsx', '.html', '.epub'}`
*   `VALID_OUTPUT_FORMATS`: `{"json", "markdown", "html", "chunks"}`
