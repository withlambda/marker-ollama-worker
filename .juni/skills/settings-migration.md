# Skill: Settings Migration — OllamaSettings to VllmSettings

## Role
Responsible for the detailed, field-by-field migration of the `OllamaSettings` Pydantic class to a new `VllmSettings` class in `settings.py`. This is the **first skill** to execute in the migration sequence.

## Scope
- Modify `settings.py` only.
- Create `VllmSettings(BaseSettings)` to replace `OllamaSettings(BaseSettings)`.
- Keep `GlobalConfig` and `MarkerSettings` intact (with targeted cleanup of Ollama-specific fields in `GlobalConfig`).

## GlobalConfig Cleanup
Remove or repurpose these Ollama-specific fields from `GlobalConfig`:

| Field | Action | Rationale |
|---|---|---|
| `ollama_models` | **Remove** | vLLM doesn't use an Ollama models directory |
| `ollama_log_dir` | **Remove** | vLLM logs via subprocess stdout/stderr capture |
| `init_environment_variables()` → `OLLAMA_MODELS`, `OLLAMA_LOG_DIR` exports | **Remove** | No longer needed |

**Keep unchanged**: All other `GlobalConfig` fields (`volume_root_mount_path`, `hf_home`, `vram_gb_total`, `vram_gb_reserve`, `vram_gb_per_token_factor`, image description markers, block correction prompts, constants).

## VllmSettings Field Mapping

### Fields migrated from OllamaSettings (with rename)

| OllamaSettings Field | VllmSettings Field | Type | Default | Notes |
|---|---|---|---|---|
| `host` | `vllm_host` | `str` | `http://127.0.0.1:8000` | Port changes from 11434 to 8000 |
| `model` | `vllm_model` | `Optional[str]` | `None` | Model name for API calls |
| `vram_gb_model` | `vllm_vram_gb_model` | `int` | *required* | VRAM consumed by the model |
| `max_retries` | `vllm_max_retries` | `int` | `3` | Retry count for failed API calls |
| `retry_delay` | `vllm_retry_delay` | `float` | `2.0` | Delay between retries (seconds) |
| `chunk_size` | `vllm_chunk_size` | `int` | `4000` | Size in **tokens** (not words) |
| `chunk_workers` | `vllm_chunk_workers` | `int` | `16` | Async tasks for parallel chunk processing |
| `block_correction_prompt_key` | `vllm_block_correction_prompt_key` | `Optional[str]` | `None` | Key into prompt library |
| `block_correction_prompt` | `vllm_block_correction_prompt` | `Optional[str]` | `None` | Custom prompt override |
| `image_description_prompt` | `vllm_image_description_prompt` | `Optional[str]` | `None` | Custom vision prompt |
| `context_length` | `vllm_max_model_len` | `int` | `16384` | Maximum context/sequence length |
| `num_parallel` | `vllm_max_num_seqs` | `int` | `16` | Max concurrent sequences |
| `log_dir` | — | — | — | **Drop**: vLLM logs via subprocess capture |
| `log_file_name` | — | — | — | **Drop**: same reason |
| `debug` | — | — | — | **Drop**: use Python logging levels instead |

### New vLLM-specific fields (no OllamaSettings equivalent)

| Field | Type | Default | Purpose |
|---|---|---|---|
| `vllm_model_path` | `DirectoryPath` | *required* | Path to model weights on disk |
| `vllm_gpu_util` | `float` | `0.90` | Max GPU memory fraction for vLLM |
| `vllm_port` | `int` | `8000` | Port for vLLM server |
| `vllm_startup_timeout` | `int` | `120` | Seconds to wait for health check |
| `vllm_vram_recovery_delay` | `int` | `10` | Seconds to wait after Marker before starting vLLM |

### OllamaSettings fields to drop (no vLLM equivalent)

| Field | Rationale |
|---|---|
| `hf_model_name` | vLLM loads models from a local path, not by HF name at runtime |
| `hf_model_quantization` | vLLM handles quantization differently (via model config) |
| `hf_home` | Managed by `GlobalConfig`, not the LLM settings |
| `models_dir` | vLLM uses `vllm_model_path` instead |
| `flash_attention` | vLLM manages attention backend internally |
| `keep_alive` | vLLM doesn't have a keep-alive concept (server runs until stopped) |
| `kv_cache_type` | vLLM manages KV cache automatically |
| `max_loaded_models` | vLLM loads one model per server instance |
| `max_queue` | vLLM manages its own request queue |

## VllmSettings Class Structure

```python
class VllmSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='VLLM_', populate_by_name=True, extra='ignore')

    # Required fields
    vllm_model_path: DirectoryPath = Field(..., validation_alias="VLLM_MODEL_PATH")
    vllm_vram_gb_model: int = Field(..., validation_alias="VLLM_VRAM_GB_MODEL")

    # Server configuration
    vllm_host: str = Field("http://127.0.0.1:8000", validation_alias="VLLM_HOST")
    vllm_port: int = Field(8000, validation_alias="VLLM_PORT")
    vllm_gpu_util: float = Field(0.90, validation_alias="VLLM_GPU_UTIL")
    vllm_max_model_len: int = Field(16384, validation_alias="VLLM_MAX_MODEL_LEN")
    vllm_max_num_seqs: int = Field(16, validation_alias="VLLM_MAX_NUM_SEQS")
    vllm_startup_timeout: int = Field(120, validation_alias="VLLM_STARTUP_TIMEOUT")
    vllm_vram_recovery_delay: int = Field(10, validation_alias="VLLM_VRAM_RECOVERY_DELAY")

    # Model selection
    vllm_model: Optional[str] = Field(None, validation_alias="VLLM_MODEL")

    # Processing configuration
    vllm_max_retries: int = Field(3, validation_alias="VLLM_MAX_RETRIES")
    vllm_retry_delay: float = Field(2.0, validation_alias="VLLM_RETRY_DELAY")
    vllm_chunk_size: int = Field(4000, validation_alias="VLLM_CHUNK_SIZE")
    vllm_chunk_workers: int = Field(16, validation_alias="VLLM_CHUNK_WORKERS")

    # Prompt configuration
    vllm_block_correction_prompt_key: Optional[str] = Field(None, ...)
    vllm_block_correction_prompt: Optional[str] = Field(None, ...)
    vllm_image_description_prompt: Optional[str] = Field(None, ...)
```

## Constructor Logic
Migrate the `__init__` logic from `OllamaSettings`:
- The VRAM-based `num_parallel` calculation should be adapted to compute `vllm_max_num_seqs` if not explicitly provided.
- The block correction prompt resolution logic (key lookup → custom prompt → skip) must be preserved.
- The `init_environment_variables` model validator should export `VLLM_*` env vars (not `OLLAMA_*`).

## Validation
- `vllm_model_path` must exist (enforced by `DirectoryPath` type).
- `vllm_gpu_util` must be between 0.0 and 1.0.
- Either `vllm_model` must be set, or the model name must be derivable from `vllm_model_path`.
- `vllm_port` must be a valid port number (1–65535).
