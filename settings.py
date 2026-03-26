"""
Configuration settings and models for the marker-vllm-worker.
This module defines the Pydantic models used to parse and validate
environment variables and job input for global, marker, and vLLM configurations.
"""
import json
import logging
import os
from pathlib import Path
from typing import Optional, ClassVar, Set

from pydantic import Field, DirectoryPath, field_validator, model_validator, AliasChoices
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
        vram_gb_total (int): Total VRAM available on GPU (used for auto-tuning worker counts).
        vram_gb_reserve (int): VRAM to reserve for system/other processes.
        vram_gb_per_token_factor (float): VRAM (GB) per token for context calculations.
        image_description_section_heading (str): Heading for a fallback image description section.
        image_description_heading (str): Marker for the beginning of image descriptions.
        image_description_end (str): Marker for the end of image descriptions.
        block_correction_prompts_file_name (str): Filename for block correction prompts JSON.
        block_correction_prompts_file_path (Path): Full path to prompts file (auto-computed).
        block_correction_prompts_library (dict): Loaded prompt templates (autoloaded from a file).

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
    LANGUAGE_DETECTION_SAMPLE_SIZE: ClassVar[int] = 2000
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
        """
        Export validated configuration fields as environment variables.

        This ensures that downstream libraries (like Hugging Face Transformers)
        that rely on specific environment variables (e.g., HF_HOME) receive
        the correctly validated and auto-computed paths.
        """
        for (prop, alias) in [
            (self.hf_home, "HF_HOME"),
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

        This method is resilient to missing or malformed files; it returns
        an empty dictionary and logs a warning/error instead of crashing.

        Args:
            block_correction_prompts_file_path: Path to the JSON library.
            file_encoding: Encoding of the file (usually UTF-8).

        Returns:
            Dictionary mapping prompt keys to their template strings.
        """
        if not block_correction_prompts_file_path.exists():
            logger.warning(f"Block correction prompt catalog not found at {block_correction_prompts_file_path}. Using empty library.")
            return {}
        try:
            with open(block_correction_prompts_file_path, 'r', encoding=file_encoding) as f:
                data = json.load(f)

            block_correction_prompt_library: dict[str, str] = {
                e["key"]: e["prompt"]
                for e in data.get("prompts", [])
                if "key" in e and "prompt" in e
            }

            logger.info(f"Loaded {len(block_correction_prompt_library)} block correction prompts from catalog")
            return block_correction_prompt_library
        except Exception as e:
            logger.error(f"Failed to load block correction prompt catalog: {e}")
            return {}



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
        output_format (str): The format of the output (Markdown, JSON, etc.).
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
    disable_maxtasksperchild: bool = Field(False, validation_alias="MARKER_DISABLE_MAXTASKSPERCHILD")

    # Worker process recycling: Number of tasks each worker handles before being recycled
    # This helps prevent memory leaks and VRAM accumulation over long-running workers.
    # Disable it by setting disable_maxtasksperchild to True.
    maxtasksperchild: Optional[int] = Field(
        default_factory=lambda data: 25 if data["disable_maxtasksperchild"] is False else None,
        validation_alias="MARKER_MAXTASKSPERCHILD"
    )


class VllmSettings(BaseSettings):
    """
    Configuration for the vLLM inference server, supporting environment variables and manual overrides.
    This class manages the lifecycle and parameters of the vLLM server.

    Fields:
        vllm_model_path (DirectoryPath): Path to model weights on disk (required).
        vllm_vram_gb_model (int): VRAM consumed by the model in GB (required).
        vllm_host (str): The host URL where the vLLM server runs.
        vllm_port (int): Port for the vLLM server.
        vllm_gpu_util (float): Maximum GPU memory fraction for vLLM (0.0–1.0).
        vllm_max_model_len (int): Maximum context/sequence length.
        vllm_max_num_seqs (int): Maximum concurrent sequences.
        vllm_startup_timeout (int): Seconds to wait for vLLM health check on startup.
        vllm_vram_recovery_delay (int): Seconds to wait after Marker before starting vLLM.
        vllm_model (str): Model name for API calls (optional, derived from vllm_model_path if not set).
        vllm_max_retries (int): Number of retries for failed API calls.
        vllm_retry_delay (float): Delay between retries in seconds.
        vllm_chunk_size (int): Size of text chunks in tokens for the correction phase.
        vllm_chunk_workers (int): Number of async tasks for parallel chunk processing.
        vllm_shutdown_grace_period (int): Seconds to wait for graceful shutdown before force-kill.
        vllm_health_check_interval (float): Polling interval in seconds for startup health checks.
        vllm_chat_completion_token_safety_margin (int): Reserved tokens for chat overhead/stop conditions.
        vllm_min_completion_tokens (int): Minimum tokens reserved for completion output.
        vllm_image_description_max_tokens (int): Upper bound for generated tokens in image descriptions.
        vllm_block_correction_prompt_key (str): Key into the prompt library (optional).
        vllm_block_correction_prompt (str): Custom block correction prompt override (optional).
        vllm_image_description_prompt (str): Custom vision prompt for image descriptions (optional).
        vllm_cpu (bool): Whether to run vLLM on CPU (default: False).
    """
    model_config = SettingsConfigDict(populate_by_name=True, extra='ignore')

    # Required fields
    vllm_model_path: Optional[DirectoryPath] = Field(
        None,
        validation_alias="MARKLLM_VLLM_MODEL_PATH"
    )
    vllm_vram_gb_model: int = Field(
        ...,
        validation_alias="MARKLLM_VLLM_VRAM_GB_MODEL"
    )

    # Server configuration
    vllm_host: str = Field("127.0.0.1", validation_alias="MARKLLM_VLLM_HOST")
    vllm_port: int = Field(8001, validation_alias="MARKLLM_VLLM_PORT")
    vllm_gpu_util: float = Field(
        0.85,
        validation_alias="MARKLLM_VLLM_GPU_UTIL"
    )
    vllm_max_model_len: int = Field(
        8192,
        validation_alias="MARKLLM_VLLM_MAX_MODEL_LEN"
    )
    vllm_max_num_seqs: int = Field(
        16,
        validation_alias="MARKLLM_VLLM_MAX_NUM_SEQS"
    )
    vllm_startup_timeout: int = Field(
        120,
        validation_alias="MARKLLM_VLLM_STARTUP_TIMEOUT",
    )
    vllm_vram_recovery_delay: int = Field(
        10,
        validation_alias="MARKLLM_VLLM_VRAM_RECOVERY_DELAY"
    )

    # Model selection
    vllm_model: Optional[str] = Field(
        None,
        validation_alias="MARKLLM_VLLM_MODEL"
    )

    # Processing configuration
    vllm_max_retries: int = Field(
        3,
        validation_alias="MARKLLM_VLLM_MAX_RETRIES"
    )
    vllm_retry_delay: float = Field(
        2.0,
        validation_alias="MARKLLM_VLLM_RETRY_DELAY"
    )
    vllm_chunk_size: int = Field(
        4000,
        validation_alias="MARKLLM_VLLM_CHUNK_SIZE"
    )
    vllm_chunk_workers: int = Field(
        16,
        validation_alias="MARKLLM_VLLM_CHUNK_WORKERS"
    )
    vllm_shutdown_grace_period: int = Field(
        10,
        validation_alias="MARKLLM_VLLM_SHUTDOWN_GRACE_PERIOD"
    )
    vllm_health_check_interval: float = Field(
        2.0,
        validation_alias="MARKLLM_VLLM_HEALTH_CHECK_INTERVAL"
    )
    vllm_chat_completion_token_safety_margin: int = Field(
        128,
        validation_alias="MARKLLM_VLLM_CHAT_COMPLETION_TOKEN_SAFETY_MARGIN"
    )
    vllm_tiktoken_encoding_name: str = Field(
        "gpt2",
        validation_alias="MARKLLM_VLLM_TIKTOKEN_ENCODING_NAME"
    )
    vllm_min_completion_tokens: int = Field(
        1,
        validation_alias="MARKLLM_VLLM_MIN_COMPLETION_TOKENS"
    )
    vllm_image_description_max_tokens: int = Field(
        1024,
        validation_alias="MARKLLM_VLLM_IMAGE_DESCRIPTION_MAX_TOKENS"
    )

    # Prompt configuration
    vllm_block_correction_prompt_key: Optional[str] = Field(
        None,
        validation_alias="MARKLLM_VLLM_BLOCK_CORRECTION_PROMPT_KEY"
    )
    vllm_block_correction_prompt: Optional[str] = Field(
        None,
        validation_alias="MARKLLM_VLLM_BLOCK_CORRECTION_PROMPT"
    )
    vllm_image_description_prompt: Optional[str] = Field(
        None,
        validation_alias="MARKLLM_VLLM_IMAGE_DESCRIPTION_PROMPT"
    )
    vllm_cpu: bool = Field(False, validation_alias="MARKLLM_VLLM_CPU")

    def __init__(
        self,
        app_config: GlobalConfig,
        **kwargs
    ):
        """Initialize VllmSettings with VRAM-based auto-tuning and prompt resolution.

        Args:
            app_config: The global application configuration providing VRAM limits,
                        and the block correction prompts library.
            **kwargs: Additional keyword arguments passed to the BaseSettings constructor.
        """
        # Capture env var state before super().__init__(), because model validators
        # make the post-init auto-calc check always see the sequence cap as already set.
        max_num_seqs_from_env = os.environ.get('MARKLLM_VLLM_MAX_NUM_SEQS')

        super().__init__(**kwargs)

        if self.vllm_cpu:
            self.vllm_max_num_seqs = 1

        # Auto-compute vllm_max_num_seqs from VRAM if not explicitly provided and not on CPU
        if 'vllm_max_num_seqs' not in kwargs and max_num_seqs_from_env is None and not self.vllm_cpu:
            # Calculate how many parallel sequences fit in remaining VRAM
            # Note: marker models are on CPU during the vLLM processing phase, so we don't subtract them
            available_vram_gb = app_config.vram_gb_total - app_config.vram_gb_reserve - self.vllm_vram_gb_model
            context_vram_gb = app_config.vram_gb_per_token_factor * self.vllm_max_model_len
            self.vllm_max_num_seqs = 1 if available_vram_gb <= 0 else max(1, int(available_vram_gb // context_vram_gb))
            logger.info(f"Calculated optimal vllm_max_num_seqs={self.vllm_max_num_seqs} "
                        f"based on VRAM/Context calculation")
            logger.info(f"VRAM/Context factors used: "
                        f"vram_gb_total={app_config.vram_gb_total}, "
                        f"vram_gb_reserve={app_config.vram_gb_reserve}, "
                        f"vram_gb_per_token_factor={app_config.vram_gb_per_token_factor}, "
                        f"vllm_vram_gb_model={self.vllm_vram_gb_model}, "
                        f"vllm_max_model_len={self.vllm_max_model_len}, "
                        f"available_vram_gb={available_vram_gb} (vram_gb_total - vram_gb_reserve - vllm_vram_gb_model), "
                        f"context_vram_gb={context_vram_gb} (vram_gb_per_token_factor * vllm_max_model_len), "
                        f"vllm_max_num_seqs={self.vllm_max_num_seqs} (available_vram_gb // context_vram_gb)")
        else:
            logger.info(f"Using provided vllm_max_num_seqs={self.vllm_max_num_seqs}")

        # Resolve the block correction prompt from library or custom override
        if not self.vllm_block_correction_prompt:
            if self.vllm_block_correction_prompt_key:
                if self.vllm_block_correction_prompt_key in app_config.block_correction_prompts_library:
                    self.vllm_block_correction_prompt = app_config.block_correction_prompts_library[self.vllm_block_correction_prompt_key]
                    logger.info(f"Using block correction prompt from catalog: '{self.vllm_block_correction_prompt_key}'")
                else:
                    logger.warning(f"Block correction prompt key '{self.vllm_block_correction_prompt_key}' not found in catalog. "
                                   f"Available keys: {list(app_config.block_correction_prompts_library.keys())}")
        else:
            logger.info(f"Using provided block correction prompt")

    @field_validator('vllm_gpu_util')
    @classmethod
    def validate_gpu_util(cls, v: float) -> float:
        """Validate that vllm_gpu_util is between 0.0 and 1.0."""
        if not 0.0 < v <= 1.0:
            raise ValueError(f"vllm_gpu_util must be between 0.0 (exclusive) and 1.0 (inclusive), got {v}")
        return v

    @field_validator('vllm_port')
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate that vllm_port is a valid port number (1–65535)."""
        if not 1 <= v <= 65535:
            raise ValueError(f"vllm_port must be between 1 and 65535, got {v}")
        return v


    @model_validator(mode='after')
    def validate_model_name(self) -> 'VllmSettings':
        """
        Ensure the vLLM model name is set.

        If MARKLLM_VLLM_MODEL is not explicitly provided, it is derived from the
        last component of the MARKLLM_VLLM_MODEL_PATH (e.g., /path/to/Llama-3-8B -> Llama-3-8B).
        This name is required for API calls to the vLLM server.

        Raises:
            ValueError: If the model name cannot be derived from the path.
        """
        if not self.vllm_model and self.vllm_model_path:
            # Derive the model name from the last component of the model path
            derived_name = Path(self.vllm_model_path).name
            if derived_name:
                self.vllm_model = derived_name
                logger.info(f"Derived vllm_model='{self.vllm_model}' from vllm_model_path")
            else:
                raise ValueError(
                    "MARKLLM_VLLM_MODEL must be set explicitly or be derivable from MARKLLM_VLLM_MODEL_PATH. "
                    "Could not derive a model name from the provided model path."
                )

        if not self.vllm_model:
            raise ValueError("MARKLLM_VLLM_MODEL must be set explicitly or be derivable from MARKLLM_VLLM_MODEL_PATH.")
        return self
