"""
Configuration settings and models for the marker-ollama-worker.
This module defines the Pydantic models used to parse and validate
environment variables and job input for global, marker, and ollama configurations.
"""
import json
import logging
import os
from pathlib import Path
from typing import Optional, ClassVar, Set

from pydantic import Field, model_validator, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

class GlobalConfig(BaseSettings):
    """
    Global application configuration loaded from environment variables.
    This class handles the core paths and behavior of the container.

    Fields:
        volume_root_mount_path (Path): The root directory where volumes are mounted.
        handler_file_name (str): The name of the handler file (default: handler.py).
        cleanup_output_dir_before_start (bool): If True, the output directory is cleared before processing.
        use_postprocess_llm (bool): Enable/Disable LLM-based post-processing.
        hf_home (Path): The home directory for Hugging Face models (auto-computed from volume_root_mount_path).
        ollama_models (Path): The directory for Ollama models (auto-computed from volume_root_mount_path).
        ollama_log_dir (Path): The directory for Ollama logs (auto-computed from volume_root_mount_path).
        vram_gb_total (int): Total VRAM available on GPU (used for auto-tuning worker counts).
        vram_gb_reserve (int): VRAM to reserve for system/other processes.
        vram_gb_per_token_factor (float): VRAM (GB) per token for context calculations.
        image_description_section_heading (str): Heading for fallback image description section.
        image_description_heading (str): Marker for beginning of image descriptions.
        image_description_end (str): Marker for end of image descriptions.
        block_correction_prompts_file_name (str): Filename for block correction prompts JSON.
        block_correction_prompts_file_path (Path): Full path to prompts file (auto-computed).
        block_correction_prompts_library (dict): Loaded prompt templates (auto-loaded from file).

    Note:
        Paths with auto-computed defaults use default_factory with validated data (Pydantic 2.10+).
        If not explicitly provided via environment variables, they are computed from volume_root_mount_path.
    """
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    volume_root_mount_path: Path = Field(..., validation_alias="VOLUME_ROOT_MOUNT_PATH", frozen=True)
    handler_file_name: str = Field("handler.py", validation_alias="HANDLER_FILE_NAME", frozen=True)
    cleanup_output_dir_before_start: bool = Field(False, validation_alias="CLEANUP_OUTPUT_DIR_BEFORE_START", frozen=True)
    use_postprocess_llm: bool = Field(True, validation_alias="USE_POSTPROCESS_LLM", frozen=True)

    hf_home: Path = Field(
        default_factory=lambda data: data["volume_root_mount_path"] / "huggingface-cache",
        validation_alias="HF_HOME",
        frozen=True
    )

    # Actual paths used by services (calculated)
    ollama_models: Path = Field(
        default_factory=lambda data: (data["volume_root_mount_path"] / ".ollama/models").resolve(),
        validation_alias="OLLAMA_MODELS",
        frozen=True
    )
    ollama_log_dir: Path = Field(
        default_factory=lambda data: (data["volume_root_mount_path"] / ".ollama/logs").resolve(),
        validation_alias="OLLAMA_LOG_DIR",
        frozen=True
    )

    # memory handling
    vram_gb_total: int = Field(..., validation_alias="VRAM_GB_TOTAL", frozen=True)
    vram_gb_reserve: int = Field(4, validation_alias="VRAM_GB_RESERVE", frozen=True)
    vram_gb_per_token_factor: float = Field(0.00013, validation_alias="VRAM_GB_PER_TOKEN_FACTOR", frozen=True)

    # image handling
    image_description_section_heading: str = Field("## Extracted Image Descriptions", validation_alias="IMAGE_DESCRIPTION_SECTION_HEADING", frozen=True)
    image_description_heading: str = Field("**[BEGIN IMAGE DESCRIPTION]**", validation_alias="IMAGE_DESCRIPTION_HEADING", frozen=True)
    image_description_end: str = Field("**[END IMAGE DESCRIPTION]**", validation_alias="IMAGE_DESCRIPTION_END", frozen=True)

    # constants
    ALLOWED_INPUT_FILE_EXTENSIONS: ClassVar[Set[str]] = {'.pdf', '.pptx', '.docx', '.xlsx', '.html', '.epub'}
    VALID_OUTPUT_FORMATS: ClassVar[Set[str]] = {"json", "markdown", "html", "chunks"}
    FORMAT_EXTENSIONS: ClassVar[dict[str, str]] = {
        "markdown": ".md",
        "json": ".json",
        "html": ".html",
        "chunks": ".txt"
    }
    FILE_ENCODING: ClassVar[str] = "utf-8"
    IMAGE_FILE_EXTENSIONS: ClassVar[Set[str]] = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}

    # block correction prompt file
    block_correction_prompts_file_name: str = Field(
        "block_correction_prompts.json",
        validation_alias="BLOCK_CORRECTION_PROMPT_FILE_NAME",
        frozen=True
    )

    block_correction_prompts_file_path: Path = Field(
        default_factory=lambda data: (Path(__file__).parent / data["block_correction_prompts_file_name"]).resolve(),
        validation_alias="BLOCK_CORRECTION_PROMPTS_FILE_PATH",
        frozen=True
    )

    block_correction_prompts_library: dict[str, str] = Field(
        default_factory=lambda data: GlobalConfig._load_block_correction_prompts(data["block_correction_prompts_file_path"], GlobalConfig.FILE_ENCODING),
        validation_alias="BLOCK_CORRECTION_PROMPTS_LIBRARY",
        frozen=True
    )

    @model_validator(mode='after')
    def init_environment_variables(self) -> 'GlobalConfig':
        """Initialize environment variables from validated fields."""
        for (prop, alias) in [
            (self.hf_home, "HF_HOME"),
            (self.ollama_models, "OLLAMA_MODELS"),
            (self.ollama_log_dir, "OLLAMA_LOG_DIR"),
        ]:
            if prop is not None and os.environ.get(alias) is None:
                os.environ[alias] = str(prop)
        return self

    @staticmethod
    def _load_block_correction_prompts(
        block_correction_prompts_file_path: Path,
        file_encoding: str
    ) -> dict[str, str]:
        """
        Loads the block correction prompt library from a JSON file.
        """
        try:
            if not block_correction_prompts_file_path.exists():
                logger.warning(f"Block correction prompt file not found: {block_correction_prompts_file_path}")
                raise FileNotFoundError(f"Block correction prompt file not found: {block_correction_prompts_file_path}")

            with open(block_correction_prompts_file_path, 'r', encoding=file_encoding) as f:
                data = json.load(f)

            block_correction_prompt_library: dict[str, str] = {}

            # Build dictionary: key -> prompt
            for entry in data.get("prompts", []):
                key = entry.get("key")
                prompt = entry.get("prompt")
                if key and prompt:
                    block_correction_prompt_library[key] = prompt

            logger.info(f"Loaded {len(block_correction_prompt_library)} block correction prompts from catalog")

            return block_correction_prompt_library
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse block correction prompts JSON: {e}")
            raise e
        except Exception as e:
            logger.error(f"Failed to load block correction prompts: {e}")
            raise e



class MarkerSettings(BaseSettings):
    """
    Configuration for the Marker PDF processing module.
    Settings are typically prefixed with 'MARKER_' in environment variables.

    Fields:
        workers (int): Number of worker processes to use for PDF conversion.
        paginate_output (bool): Whether to paginate the output text.
        force_ocr (bool): Force OCR on all pages.
        disable_multiprocessing (bool): Disable internal multiprocessing of Marker.
        disable_image_extraction (bool): Do not extract images from documents.
        page_range (str): Specific pages to process (e.g., "1-5,8").
        processors (str): Comma-separated list of marker processors to run.
        output_format (str): The format of the output (markdown, json, etc.).
        vram_gb_per_worker (int): The amount of VRAM (in GB) to allocate per worker process.
        debug (bool): Enable debug mode for detailed logging.
        maxtasksperchild (int): Number of tasks each worker handles before recycling.
                                This prevents memory leaks and VRAM accumulation.
    """
    model_config = SettingsConfigDict(env_prefix='MARKER_', populate_by_name=True, extra='ignore')

    workers: Optional[int] = Field(None, validation_alias="MARKER_WORKERS")
    paginate_output: bool = Field(False, validation_alias="MARKER_PAGINATE_OUTPUT")
    force_ocr: bool = Field(False, validation_alias="MARKER_FORCE_OCR")
    disable_multiprocessing: bool = Field(False, validation_alias="MARKER_DISABLE_MULTIPROCESSING")
    disable_image_extraction: bool = Field(False, validation_alias="MARKER_DISABLE_IMAGE_EXTRACTION")
    page_range: Optional[str] = Field(None, validation_alias="MARKER_PAGE_RANGE")
    processors: Optional[str] = Field(None, validation_alias="MARKER_PROCESSORS")
    output_format: str = Field("markdown", validation_alias="MARKER_OUTPUT_FORMAT")
    vram_gb_per_worker: int = Field(5, validation_alias="MARKER_VRAM_GB_PER_WORKER")
    debug: bool = Field(False, validation_alias="MARKER_DEBUG")
    # Worker process recycling: Number of tasks each worker handles before being recycled
    # This helps prevent memory leaks and VRAM accumulation over long-running workers
    maxtasksperchild: int = Field(10, validation_alias="MARKER_MAXTASKSPERCHILD")



class OllamaSettings(BaseSettings):
    """
    Configuration for the Ollama worker, supporting environment variables and manual overrides.
    This class manages the lifecycle and parameters of the Ollama server and models.

    Fields:
        host (str): The host and port where Ollama server runs.
        model (str): The specific Ollama model to use.
        hf_model_name (str): The Hugging Face model identifier for building Ollama models.
        hf_model_quantization (str): The quantization type for the Hugging Face model.
        hf_home (str): Home directory for Hugging Face cache.
        models_dir (str): Directory where Ollama models are stored.
        max_retries (int): Number of retries for failed API calls.
        retry_delay (float): Delay between retries in seconds.
        chunk_size (int): Size of text chunks to process in the correction phase.
        image_description_prompt (str): Custom prompt for image descriptions.
        flash_attention (str): Enable/Disable flash attention in Ollama server.
        keep_alive (str): How long to keep models in memory.
        log_dir (str): Directory for Ollama server logs.
        debug (str): Enable/Disable debug mode in Ollama.
        num_parallel (int): Number of parallel requests Ollama server should handle.
        max_loaded_models (int): Max models to load in memory concurrently.
        kv_cache_type (str): The KV cache type (e.g., fp16, q4_0, q8_0).
        max_queue (int): Max number of requests in queue.
        context_length (int): Maximum context length for the LLM.
    """
    model_config = SettingsConfigDict(env_prefix='OLLAMA_', populate_by_name=True, extra='ignore')

    host: str = Field(
        "http://127.0.0.1:11434",
        validation_alias=AliasChoices("OLLAMA_HOST", "OLLAMA_BASE_URL")
    )
    # Model configuration
    model: Optional[str] = Field(None, validation_alias="OLLAMA_MODEL")
    hf_model_name: Optional[str] = Field(None, validation_alias="OLLAMA_HUGGING_FACE_MODEL_NAME")
    hf_model_quantization: Optional[str] = Field(None, validation_alias="OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION")
    # the size of model in GB, must be provided!
    vram_gb_model: int = Field(..., validation_alias="OLLAMA_VRAM_GB_MODEL")
    hf_home: Optional[str] = Field(None, validation_alias="HF_HOME")
    models_dir: Optional[str] = Field(None, validation_alias="OLLAMA_MODELS")

    # Runtime configuration
    max_retries: int = Field(3, validation_alias="OLLAMA_MAX_RETRIES")
    retry_delay: float = Field(2.0, validation_alias="OLLAMA_RETRY_DELAY")
    chunk_size: int = Field(4000, validation_alias="OLLAMA_CHUNK_SIZE")
    block_correction_prompt_key: Optional[str] = Field(None, validation_alias="OLLAMA_BLOCK_CORRECTION_PROMPT_KEY")
    block_correction_prompt: Optional[str] = Field(None, validation_alias="OLLAMA_BLOCK_CORRECTION_PROMPT")
    image_description_prompt: Optional[str] = Field(None, validation_alias="OLLAMA_IMAGE_DESCRIPTION_PROMPT")

    # Server configuration (used when starting the server)
    flash_attention: str = Field("1", validation_alias="OLLAMA_FLASH_ATTENTION")
    keep_alive: str = Field("-1", validation_alias="OLLAMA_KEEP_ALIVE")
    log_dir: str = Field(".", validation_alias="OLLAMA_LOG_DIR")
    log_file_name: str = Field("ollama.log", validation_alias="OLLAMA_LOG_FILE_NAME")
    debug: str = Field("0", validation_alias="OLLAMA_DEBUG")
    num_parallel: Optional[int] = Field(None, validation_alias="OLLAMA_NUM_PARALLEL")
    max_loaded_models: Optional[int] = Field(None, validation_alias="OLLAMA_MAX_LOADED_MODELS")
    kv_cache_type: Optional[str] = Field(None, validation_alias="OLLAMA_KV_CACHE_TYPE")
    max_queue: Optional[int] = Field(None, validation_alias="OLLAMA_MAX_QUEUE")
    context_length: int = Field(4096, validation_alias="OLLAMA_CONTEXT_LENGTH")

    # Processing

    # ollama_chunk_workers (Python threads) should be decoupled and saturated
    # We can set a higher default to ensure the Ollama queue is always full.
    # Default to 16, but respect existing user overrides if they come later.
    chunk_workers: int = Field(16, validation_alias="OLLAMA_CHUNK_WORKERS")

    def __init__(
        self,
        app_config: GlobalConfig,
        **kwargs
    ):
        super().__init__(**kwargs)
        if self.num_parallel is None:
            # Calculate how many parallel contexts fit in remaining VRAM
            # Note: marker models are on CPU during the Ollama processing phase, so we don't subtract them
            available_vram_gb = app_config.vram_gb_total - app_config.vram_gb_reserve - self.vram_gb_model
            context_vram_gb = app_config.vram_gb_per_token_factor * self.context_length
            self.num_parallel = 1 if available_vram_gb <= 0 else max(1, int(available_vram_gb // context_vram_gb))
            logger.info(f"Calculated the following optimal number of parallel requests for the Ollama server, "
                        "based on VRAM/Context calculation: "
                        f"ollama_num_parallel={self.num_parallel}")

        # determine the block correction prompt
        if not self.block_correction_prompt:
            if self.block_correction_prompt_key:
                if self.block_correction_prompt_key in app_config.block_correction_prompts_library:
                    self.block_correction_prompt = app_config.block_correction_prompts_library[self.block_correction_prompt_key]
                    logger.info(f"Using block correction prompt from catalog: '{self.block_correction_prompt_key}'")
                else:
                    logger.warning(f"Block correction prompt key '{self.block_correction_prompt_key}' not found in catalog. "
                                   f"Available keys: {list(app_config.block_correction_prompts_library.keys())}")
        else:
            logger.info(f"Using provided block correction prompt")

    @model_validator(mode='after')
    def init_environment_variables(self) -> 'OllamaSettings':
        for  (prop, alias) in [
            (self.host, "OLLAMA_HOST"),
            (self.models_dir, "OLLAMA_MODELS"),
            (self.hf_home, "HF_HOME"),
            (self.flash_attention, "OLLAMA_FLASH_ATTENTION"),
            (self.keep_alive, "OLLAMA_KEEP_ALIVE"),
            (self.debug, "OLLAMA_DEBUG"),
            (self.num_parallel, "OLLAMA_NUM_PARALLEL"),
            (self.max_loaded_models, "OLLAMA_MAX_LOADED_MODELS"),
            (self.kv_cache_type, "OLLAMA_KV_CACHE_TYPE"),
            (self.max_queue, "OLLAMA_MAX_QUEUE"),
            (self.context_length, "OLLAMA_CONTEXT_LENGTH"),
        ]:
            if prop is not None and os.environ.get(alias) is None:
                os.environ[alias] = str(prop)
        return self

    @model_validator(mode='after')
    def validation(self) -> 'OllamaSettings':
        """
        Validation of the OllamaSettings object.
        """
        # OLLAMA_MODEL validation for post-processing
        if not self.model:
            if not (self.hf_model_name and self.hf_model_quantization):
                raise ValueError(
                    "OLLAMA_HUGGING_FACE_MODEL_NAME and OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION environment variables "
                    "or the corresponding json keys in the JSON request input to the handler "
                    "must be defined when OLLAMA_MODEL environment variable or ollama_model JSON request input "
                    "to the handler is not set."
                )
        return self
