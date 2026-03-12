# `handler.py`

## Context
This file serves as the main entry point for the RunPod Serverless worker. It processes input documents using `marker-pdf` and optionally enhances the output using a local Ollama LLM. It is designed to run inside the Docker container defined for this project.

## Interfaces

### Classes

#### `TextProcessor`
A utility class for processing text inputs, primarily for parsing configuration values.

*   `is_allowed_type_for_parsing(value)`: Checks if the value is a string, integer, or float. Raises `TypeError` otherwise.
*   `to_bool(value)`: Converts a value (boolean, string, or number) to a boolean. Returns `True` for 'true', '1', 'yes', 'on', and `False` for 'false', '0', 'no', 'off', 'None', or empty string. Raises `ValueError` if not parsable.
*   `is_parseable_as_int(value)`: Checks if a value can be parsed as an integer. Returns `True` or raises `ValueError`.

### Functions

#### `check_and_pull_model(model_name)`
Checks if the specified Ollama model exists locally. If not, it attempts to pull it from the registry.
*   **Args**: `model_name` (str) - The name of the Ollama model.
*   **Returns**: `bool` - `True` if successful.
*   **Raises**: `RuntimeError` if the model cannot be found or pulled.

#### `load_models()`
Loads marker models into memory (VRAM) if not already loaded (Warm Start). It uses the global `ARTIFACT_DICT`.

#### `check_is_dir(path)`
Checks if the given path is a directory. Raises `NotADirectoryError` if not.

#### `check_is_not_file(path)`
Checks if the given path is not a file. Raises `ValueError` if it is.

#### `check_no_subdirs(path)`
Checks if the directory at the given path contains any subdirectories (ignoring hidden ones). Raises `ValueError` if subdirectories exist.

#### `is_empty_dir(path)`
Checks if a directory is empty (ignoring hidden files). Returns `bool`.

#### `check_is_empty_dir(path)`
Checks if the directory at the given path is empty. Raises `ValueError` if not.

#### `validate_document_formats(directory_path, allowed_file_extensions)`
Validates that all files in the directory have allowed extensions. Raises `ValueError` if unsupported formats are found.

#### `process_single_file(file_path, converter, output_base_path)`
Processes a single file using the provided `marker` converter and saves the output (Markdown, JSON metadata, images) to a subfolder in the output directory.

#### `handler(job)`
The main RunPod handler function.
*   **Args**: `job` (dict) - The job payload containing `input` configuration.
*   **Returns**: `dict` - Status and message.
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
6.  **Cleanup**:
    *   Deletes processed input files to save space/indicate completion.
7.  **Return**:
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
