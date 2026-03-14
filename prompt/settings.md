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
*   `HF_HOME` (Optional[Path]): Hugging Face home directory.
*   `OLLAMA_MODELS_DIR` (str): Relative directory for Ollama models.
*   `OLLAMA_LOGS_DIR` (str): Relative directory for Ollama logs.

### `MarkerSettings(BaseModel)`
Configuration for the Marker PDF processing, typically extracted from job input.
*   `workers` (Optional[int])
*   `paginate_output` (bool)
*   `force_ocr` (bool)
*   `disable_multiprocessing` (bool)
*   `disable_image_extraction` (bool)
*   `page_range` (Optional[str])
*   `processors` (Optional[str])
*   `output_format` (str)

### `OllamaSettings(BaseSettings)`
Configuration for the Ollama worker, supporting environment variables (prefixed with `OLLAMA_`) and manual overrides.
*   `host` (str): Ollama server host.
*   `model` (Optional[str]): Ollama model name.
*   `max_retries` (int)
*   `retry_delay` (float)
*   `context_length` (int)
*   `flash_attention` (str)
*   `keep_alive` (str)
*   `log_dir` (Optional[str])
*   `debug` (str)
*   `hf_model_name` (Optional[str])
*   `hf_model_quantization` (Optional[str])
*   `num_parallel` (Optional[int])
*   `max_loaded_models` (Optional[int])
*   `kv_cache_type` (Optional[str])
*   `max_queue` (int)
*   `chunk_size` (int)
*   `models_dir` (Optional[str])
*   `hf_home` (Optional[str])

## Logic
*   Uses `pydantic-settings` to automatically load values from the environment.
*   Calculates absolute paths for `ollama_models`, `ollama_logs`, and `hf_home` based on `volume_root_mount_path`.
*   Provides a structured way to handle job-specific overrides for both Marker and Ollama.
