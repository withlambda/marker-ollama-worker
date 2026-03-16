# prompt/settings.py

This file defines the configuration and settings for the marker-ollama-worker using Pydantic.

## Context
The file is located at the root of the project and is used to load, validate, and manage configuration from environment variables and job inputs.

## Interface

### `GlobalConfig(BaseSettings)`
Global application configuration loaded from environment variables.
*   `VOLUME_ROOT_MOUNT_PATH` (Path): Root path of network volume.
*   `HANDLER_FILE_NAME` (str): Name of the handler file.
*   `CLEANUP_OUTPUT_DIR_BEFORE_START` (bool): Whether to cleanup the output directory before starting.
*   `USE_POSTPROCESS_LLM` (bool): Whether to use an LLM for post-processing.
*   `HF_HOME` (Path): Hugging Face home directory (auto-computed from volume root via default_factory if not set).
*   `OLLAMA_MODELS` (Path): Ollama models directory (auto-computed from volume root via default_factory if not set).
*   `OLLAMA_LOG_DIR` (Path): Ollama logs directory (auto-computed from volume root via default_factory if not set).
*   `block_correction_prompts_file_path` (Path): Path to prompts JSON file (auto-computed via default_factory).
*   `block_correction_prompts_library` (dict[str, str]): Loaded prompt templates (auto-loaded from file via default_factory).

**Note**: Paths with auto-computed defaults use `default_factory` with validated data (requires Pydantic 2.10+).

### `MarkerSettings(BaseModel)`
Configuration for the Marker PDF processing, typically extracted from job input.
*   `workers` (Optional[int]): `MARKER_WORKERS`
*   `paginate_output` (bool): `MARKER_PAGINATE_OUTPUT`
*   `force_ocr` (bool): `MARKER_FORCE_OCR`
*   `disable_multiprocessing` (bool): `MARKER_DISABLE_MULTIPROCESSING`
*   `disable_image_extraction` (bool): `MARKER_DISABLE_IMAGE_EXTRACTION`
*   `page_range` (Optional[str]): `MARKER_PAGE_RANGE`
*   `processors` (Optional[str]): `MARKER_PROCESSORS`
*   `output_format` (str): `MARKER_OUTPUT_FORMAT`
*   `maxtasksperchild` (int): `MARKER_MAXTASKSPERCHILD` - Number of tasks per worker before recycling (default: 10)

### `OllamaSettings(BaseSettings)`
Configuration for the Ollama worker, supporting environment variables (prefixed with `OLLAMA_`) and manual overrides.
*   `host` (str): `OLLAMA_HOST` (also `OLLAMA_BASE_URL`)
*   `model` (Optional[str]): `OLLAMA_MODEL`
*   `max_retries` (int): `OLLAMA_MAX_RETRIES`
*   `retry_delay` (float): `OLLAMA_RETRY_DELAY`
*   `context_length` (int): `OLLAMA_CONTEXT_LENGTH`
*   `flash_attention` (str): `OLLAMA_FLASH_ATTENTION`
*   `keep_alive` (str): `OLLAMA_KEEP_ALIVE`
*   `log_dir` (Optional[str]): `OLLAMA_LOG_DIR` (also `OLLAMA_LOG_DIR`)
*   `debug` (str): `OLLAMA_DEBUG`
*   `hf_model_name` (Optional[str]): `OLLAMA_HUGGING_FACE_MODEL_NAME`
*   `hf_model_quantization` (Optional[str]): `OLLAMA_HF_MODEL_QUANTIZATION` (also `OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION`)
*   `num_parallel` (Optional[int]): `OLLAMA_NUM_PARALLEL`
*   `max_loaded_models` (Optional[int]): `OLLAMA_MAX_LOADED_MODELS`
*   `kv_cache_type` (Optional[str]): `OLLAMA_KV_CACHE_TYPE`
*   `max_queue` (Optional[int]): `OLLAMA_MAX_QUEUE`
*   `chunk_size` (int): `OLLAMA_CHUNK_SIZE`
*   `image_description_prompt` (Optional[str]): `OLLAMA_IMAGE_DESCRIPTION_PROMPT`
*   `models_dir` (Optional[str]): `OLLAMA_MODELS`
*   `hf_home` (Optional[str]): `OLLAMA_HF_HOME` (also `HF_HOME`)

## Logic
*   Uses `pydantic-settings` to automatically load values from the environment.
*   Calculates absolute paths for `ollama_models`, `ollama_log_dir`, and `hf_home` based on `volume_root_mount_path` using Pydantic's `default_factory` with validated data (requires Pydantic 2.10+).
*   Provides a structured way to handle job-specific overrides for both Marker and Ollama.
*   Input validation warns users about unknown `marker_*` or `ollama_*` keys to help catch typos.
