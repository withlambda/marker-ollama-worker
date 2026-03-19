# Context
This file, `settings.py`, defines the configuration and data validation layer for the marker-vllm-worker. It uses Pydantic (v2) and Pydantic-Settings to parse, validate, and auto-compute settings from environment variables and job inputs. It is the central authority for all parameters related to global paths, memory management, Marker processing, and vLLM server lifecycle.

# Interface

## Classes

### GlobalConfig(BaseSettings)
Main application configuration, primarily for system-level paths and VRAM orchestration.
- **Environment Variables**:
  - `VOLUME_ROOT_MOUNT_PATH` (Required): Root directory for all persistent data.
  - `HANDLER_FILE_NAME` (Default: "handler.py"): Name of the handler entry point.
  - `CLEANUP_OUTPUT_DIR_BEFORE_START` (Default: False): Whether to purge output dir.
  - `USE_POSTPROCESS_LLM` (Default: True): Toggle for the LLM phase.
  - `HF_HOME` (Computed): Path for Hugging Face cache, defaults to `VOLUME_ROOT_MOUNT_PATH/huggingface-cache`.
  - `VRAM_GB_TOTAL` (Required): Total GPU memory available.
  - `VRAM_GB_RESERVE` (Default: 4): Memory to keep free for system overhead.
  - `VRAM_GB_PER_TOKEN_FACTOR` (Default: 0.00013): VRAM usage per token for context calculation.
  - `IMAGE_DESCRIPTION_SECTION_HEADING` (Default: "## Extracted Image Descriptions").
  - `IMAGE_DESCRIPTION_HEADING` (Default: "**[BEGIN IMAGE DESCRIPTION]**").
  - `IMAGE_DESCRIPTION_END` (Default: "**[END IMAGE DESCRIPTION]**").
  - `BLOCK_CORRECTION_PROMPT_FILE_NAME` (Default: "block_correction_prompts.json").
- **Properties**:
  - `ALLOWED_INPUT_FILE_EXTENSIONS`: {'.pdf', '.pptx', '.docx', '.xlsx', '.html', '.epub'}
  - `VALID_OUTPUT_FORMATS`: {"json", "markdown", "html", "chunks"}
  - `FORMAT_EXTENSIONS`: Mapping of formats to extensions (e.g., "markdown" -> ".md").
  - `IMAGE_FILE_EXTENSIONS`: {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}

### MarkerSettings(BaseSettings)
Configuration for the Marker PDF-to-Markdown engine.
- **Environment Prefix**: `MARKER_`
- **Fields**:
  - `MARKER_WORKERS` (Optional): Number of parallel marker processes.
  - `MARKER_PAGINATE_OUTPUT` (Default: False).
  - `MARKER_FORCE_OCR` (Default: False).
  - `MARKER_DISABLE_MULTIPROCESSING` (Default: False).
  - `MARKER_DISABLE_IMAGE_EXTRACTION` (Default: False).
  - `MARKER_PAGE_RANGE` (Optional): e.g., "1-5".
  - `MARKER_PROCESSORS` (Optional): Comma-separated processor list.
  - `MARKER_OUTPUT_FORMAT` (Default: "markdown").
  - `MARKER_VRAM_GB_PER_WORKER` (Default: 5).
  - `MARKER_DEBUG` (Default: False).
  - `MARKER_MAXTASKSPERCHILD` (Default: 10): Recycling limit to prevent memory leaks.

### VllmSettings(BaseSettings)
Configuration for the vLLM inference server.
- **Environment Prefix**: `VLLM_`
- **Fields**:
  - `VLLM_MODEL_PATH` (Required): Path to model weights on disk.
  - `VLLM_VRAM_GB_MODEL` (Required): VRAM size of the model itself.
  - `VLLM_HOST` (Default: "http://127.0.0.1:8000").
  - `VLLM_PORT` (Default: 8000).
  - `VLLM_GPU_UTIL` (Default: 0.90): Max memory fraction.
  - `VLLM_MAX_MODEL_LEN` (Default: 16384).
  - `VLLM_MAX_NUM_SEQS` (Computed): Concurrency limit.
  - `VLLM_STARTUP_TIMEOUT` (Default: 120): Seconds to wait for server.
  - `VLLM_VRAM_RECOVERY_DELAY` (Default: 10): Wait time after Marker phase.
  - `VLLM_MODEL` (Derived): Model name for API calls.
  - `VLLM_MAX_RETRIES` (Default: 3).
  - `VLLM_RETRY_DELAY` (Default: 2.0).
  - `VLLM_CHUNK_SIZE` (Default: 4000): Tokens per processing chunk.
  - `VLLM_CHUNK_WORKERS` (Default: 16): Parallel async tasks.
  - `VLLM_BLOCK_CORRECTION_PROMPT_KEY` (Optional).
  - `VLLM_BLOCK_CORRECTION_PROMPT` (Optional): Direct template override.
  - `VLLM_IMAGE_DESCRIPTION_PROMPT` (Optional): Vision prompt.

# Logic

### GlobalConfig Initialization
1.  **Environment Loading**: Uses `SettingsConfigDict` to load from `.env` and environment variables.
2.  **Auto-computation**:
    - `hf_home` is set to `volume_root_mount_path / "huggingface-cache"`.
    - `block_correction_prompts_file_path` is resolved relative to the script's directory.
    - `block_correction_prompts_library` is loaded by reading the JSON file at `block_correction_prompts_file_path`. If the file is missing or invalid, it returns an empty dictionary.
3.  **Environment Export**: Post-validation, `HF_HOME` is exported to `os.environ` to ensure downstream libraries use the correct path.

### VllmSettings Initialization
1.  **VRAM-based Auto-tuning**:
    - If `VLLM_MAX_NUM_SEQS` is not explicitly provided in environment or constructor:
      - `available_vram_gb` = `GlobalConfig.vram_gb_total` - `GlobalConfig.vram_gb_reserve` - `VLLM_VRAM_GB_MODEL`.
      - `context_vram_gb` = `GlobalConfig.vram_gb_per_token_factor` * `VLLM_MAX_MODEL_LEN`.
      - `VLLM_MAX_NUM_SEQS` = `max(1, available_vram_gb // context_vram_gb)`.
2.  **Prompt Resolution**:
    - If `vllm_block_correction_prompt` is not set:
      - If `vllm_block_correction_prompt_key` exists and is in the `app_config.block_correction_prompts_library`, use that template.
3.  **Model Name Derivation**:
    - If `VLLM_MODEL` is not set, use the `.name` property (last component) of `VLLM_MODEL_PATH`.
4.  **Validation**:
    - `vllm_gpu_util` must be in (0.0, 1.0].
    - `vllm_port` must be in [1, 65535].
5.  **Environment Export**: Validated settings (`VLLM_HOST`, `VLLM_PORT`, etc.) are exported to `os.environ` for use by subprocesses.

# Goal
The prompt file provides the structure and logic necessary to regenerate `settings.py` exactly as it is now, including all Pydantic models, validation rules, auto-tuning math, and environment variable mapping.
