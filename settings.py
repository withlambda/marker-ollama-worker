from pathlib import Path
from typing import Optional

from pydantic import Field, model_validator, BaseModel, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class GlobalConfig(BaseSettings):
    """
    Global application configuration loaded from environment variables.
    """
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    volume_root_mount_path: Path = Field(..., validation_alias="VOLUME_ROOT_MOUNT_PATH")
    handler_file_name: str = Field("handler.py", validation_alias="HANDLER_FILE_NAME")
    cleanup_output_dir_before_start: bool = Field(False, validation_alias="CLEANUP_OUTPUT_DIR_BEFORE_START")
    use_postprocess_llm: bool = Field(True, validation_alias="USE_POSTPROCESS_LLM")

    # Path configuration
    hf_home: Optional[Path] = Field(None, validation_alias="HF_HOME")
    ollama_models_dir_rel: str = Field("/.ollama/models", validation_alias="OLLAMA_MODELS_DIR")
    ollama_logs_dir_rel: str = Field("/.ollama/logs", validation_alias="OLLAMA_LOGS_DIR")

    # Actual paths used by services (calculated)
    ollama_models: Optional[Path] = Field(None, validation_alias="OLLAMA_MODELS")
    ollama_logs: Optional[Path] = Field(None, validation_alias="OLLAMA_LOGS")

    @model_validator(mode='after')
    def setup_paths(self) -> 'GlobalConfig':
        if not self.hf_home:
            self.hf_home = self.volume_root_mount_path / "huggingface-cache"

        if not self.ollama_models:
            self.ollama_models = (self.volume_root_mount_path / self.ollama_models_dir_rel.lstrip("/")).resolve()

        if not self.ollama_logs:
            self.ollama_logs = (self.volume_root_mount_path / self.ollama_logs_dir_rel.lstrip("/")).resolve()

        return self

class MarkerSettings(BaseModel):
    """
    Configuration for the Marker PDF processing.
    """
    workers: Optional[int] = None
    paginate_output: bool = False
    force_ocr: bool = False
    disable_multiprocessing: bool = False
    disable_image_extraction: bool = False
    page_range: Optional[str] = None
    processors: Optional[str] = None
    output_format: str = "markdown"

class OllamaSettings(BaseSettings):
    """
    Configuration for the Ollama worker, supporting environment variables and manual overrides.
    """
    model_config = SettingsConfigDict(env_prefix='OLLAMA_', extra='ignore')

    host: str = Field(
        "http://127.0.0.1:11434",
        validation_alias=AliasChoices("OLLAMA_HOST", "OLLAMA_BASE_URL")
    )
    model: Optional[str] = Field(None)
    max_retries: int = Field(3)
    retry_delay: float = Field(2.0)
    context_length: int = Field(4096)
    flash_attention: str = Field("1")
    keep_alive: str = Field("-1")
    log_dir: Optional[str] = Field(None, validation_alias="OLLAMA_LOGS")
    debug: str = Field("0")
    hf_model_name: Optional[str] = Field(None, validation_alias="OLLAMA_HUGGING_FACE_MODEL_NAME")
    hf_model_quantization: Optional[str] = Field(None, validation_alias="OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION")
    num_parallel: Optional[int] = Field(None)
    max_loaded_models: Optional[int] = Field(None)
    kv_cache_type: Optional[str] = Field(None)
    max_queue: Optional[int] = Field(None)
    chunk_size: int = Field(4000)
    image_description_prompt: Optional[str] = Field(None, validation_alias="OLLAMA_IMAGE_DESCRIPTION_PROMPT")
    models_dir: Optional[str] = Field(None, validation_alias="OLLAMA_MODELS")
    hf_home: Optional[str] = Field(None, validation_alias="HF_HOME")

    @model_validator(mode='after')
    def validate_hf_model(self) -> 'OllamaSettings':
        # If model is not set, hf_model_name and hf_model_quantization must be set
        # But this depends on whether use_postprocess_llm is true, which is in GlobalConfig
        # We'll do this validation in the handler or a combined validator if needed.
        return self

# Initialize global config
global_config = None
try:
    global_config = GlobalConfig()
except Exception:
    # This might fail during initialization if env vars are missing
    # but we'll handle it in setup_config
    pass
