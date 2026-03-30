# Copyright (C) 2026 withLambda
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Utility functions and classes for the mineru-vllm-worker.
Includes environment configuration, resource management (VRAM),
and path validation utilities.
"""

import math
import logging
import os
from PIL import Image
from transformers import AutoConfig, AutoTokenizer
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Tuple, Union, Optional

from huggingface_hub import try_to_load_from_cache, _CACHED_NO_EXIST

from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException

from settings import GlobalConfig

logger = logging.getLogger(__name__)

# Set seed for deterministic language detection
DetectorFactory.seed = 0

def setup_config() -> GlobalConfig:
    """
    Validates and configures environment variables and ensures required directories exist.

    This function:
    1. Instantiates GlobalConfig, which performs Pydantic validation of environment variables.
    2. Ensures that directories for Hugging Face cache exist.
    3. Sets environment variables for downstream libraries (HF).
    4. Handles ownership and permission updates if running as root.
    5. Validates additional model-related configuration for post-processing.

    Returns:
        GlobalConfig: The validated global configuration object.

    Raises:
        ValidationError: If environment variables fail Pydantic validation.
        ValueError: If mandatory model configurations are missing when LLM is enabled.
    """
    try:
        config = GlobalConfig()
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        raise

    if config.use_postprocess_llm:
        # Ensure directories exist
        os.makedirs(config.hf_home, exist_ok=True)
        # Ownership/Permissions (if root)
        # Note: This assumes Linux/Docker environment where UID 0 is root
        # This is required to allow non-root user (appuser) to access mounted volumes
        if os.getuid() == 0:
            _update_ownership(
                str(config.hf_home)
            )

    return config

def _update_ownership(*paths: str) -> None:
    """
    Updates ownership of the specified paths to appuser:appgroup if they exist.

    This is used when running as root (e.g., in a container) to ensure the
    non-root user can access mounted volumes.

    Args:
        *paths: Variable length list of directory/file paths to update.
    """
    try:
        # Check if appuser exists
        subprocess.run(["id", "appuser"], capture_output=True, check=True)

        logger.info(f"Updating ownership of {', '.join(paths)} to appuser...")
        for path in paths:
            # chown -R --silent appuser:appgroup "$path" || true
            subprocess.run(["chown", "-R", "--silent", "appuser:appgroup", path], check=False)

            # Fallback check
            # We use gosu to test write access as appuser
            res = subprocess.run(["gosu", "appuser", "test", "-w", path], capture_output=True, check=False)
            if res.returncode != 0:
                logger.warning(f"Warning: Could not change ownership of {path}. Trying chmod as fallback...")
                subprocess.run(["chmod", "-R", "775", path], stderr=subprocess.DEVNULL, check=False)
    except (subprocess.CalledProcessError, FileNotFoundError):
        # appuser does not exist or id/gosu command not found
        pass

def get_vram_info() -> Dict[str, Any]:
    """
    Attempts to get VRAM information using nvidia-smi.

    Returns:
        Dict[str, Any]: A dictionary containing 'total', 'used', and 'free' VRAM in MB.
                        Returns an empty dictionary if nvidia-smi is not available.
    """
    try:
        res = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used,memory.free", "--format=csv,nounits,noheader"],
            encoding="utf-8"
        )
        total, used, free = map(int, res.strip().split(","))
        return {"total": total, "used": used, "free": free}
    except Exception as e:
        logger.debug(f"Could not get VRAM info: {e}")
        return {}

def log_vram_usage(label: str = "") -> None:
    """
    Logs the current VRAM usage to the logger.

    Args:
        label (str): An optional label to include in the log message.
    """
    info = get_vram_info()
    if info:
        logger.info(f"VRAM Usage {f'({label})' if label else ''}: "
                    f"Total: {info['total']}MB, Used: {info['used']}MB, Free: {info['free']}MB")
    else:
        logger.info(f"VRAM Usage {f'({label})' if label else ''}: nvidia-smi not available.")

def check_is_dir(path: Union[str, Path]) -> None:
    """
    Checks if the given path is a directory.

    Args:
        path (Union[str, Path]): Path to check.

    Raises:
        NotADirectoryError: If the path does not exist or is not a directory.
    """
    if not os.path.isdir(path):
        raise NotADirectoryError(f"Path '{path}' is not a directory.")

def check_is_not_file(path: Union[str, Path]) -> None:
    """
    Checks if the given path is NOT a file.

    Args:
        path (Union[str, Path]): Path to check.

    Raises:
        ValueError: If the path is an existing file.
    """
    if os.path.isfile(path):
        raise ValueError(f"Path '{path}' is a file.")

def check_no_subdirs(path: Union[str, Path]) -> None:
    """
    Checks if the given directory contains no subdirectories (excluding hidden ones).

    Args:
        path (Union[str, Path]): Path to the directory to check.

    Raises:
        ValueError: If subdirectories are found.
    """
    subdir_count = sum(1 for entry in os.scandir(path) if entry.is_dir() and not entry.name.startswith('.'))
    if subdir_count > 0:
        raise ValueError(f"Path '{path}' contains subdirectories.")

def is_empty_dir(path: Union[str, Path]) -> bool:
    """
    Checks if the given path is an empty directory (excluding hidden files).

    Args:
        path (Union[str, Path]): Path to check.

    Returns:
        bool: True if empty, False otherwise.
    """
    p = Path(path)
    if not p.is_dir():
        return False
    for item in p.iterdir():
        if not item.name.startswith('.'):
            return False
    return True

def check_is_empty_dir(path: Union[str, Path]) -> None:
    """
    Checks if the given path is an empty directory if it exists.

    Args:
        path (Union[str, Path]): Path to check.

    Raises:
        ValueError: If the directory exists and is not empty.
    """
    if os.path.exists(path) and not is_empty_dir(path):
        raise ValueError(f"Directory '{path}' is not empty.")

def clear_directory(path: Union[str, Path]) -> None:
    """
    Deletes all contents of a directory without removing the directory itself.

    This is useful for cleaning up mounted volumes where removing the root
    directory would fail with 'Device or resource busy'.

    Args:
        path (Union[str, Path]): Path to the directory to clear.
    """
    path = Path(path)
    if not path.is_dir():
        return

    logger.info(f"Clearing contents of directory: {path}")
    for item in path.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        except Exception as e:
            logger.warning(f"Failed to delete {item} during directory cleanup: {e}")

class LanguageProcessor:
    """
    A utility class for language detection and localization.
    """
    _LANGUAGE_NAME_MAP = {
        "en": "English",
        "de": "German",
        "fr": "French",
        "es": "Spanish",
        "it": "Italian",
        "pt": "Portuguese",
        "nl": "Dutch",
        "pl": "Polish",
        "cs": "Czech",
        "ru": "Russian",
    }

    _LOCALIZED_LABELS = {
        "en": {
            "section_heading": "## Extracted Image Descriptions",
            "begin_marker": "**[BEGIN IMAGE DESCRIPTION]**",
            "end_marker": "**[END IMAGE DESCRIPTION]**",
        },
        "de": {
            "section_heading": "## Extrahierte Bildbeschreibungen",
            "begin_marker": "**[BEGINN BILDBESCHREIBUNG]**",
            "end_marker": "**[ENDE BILDBESCHREIBUNG]**",
        },
        "fr": {
            "section_heading": "## Descriptions d'images extraites",
            "begin_marker": "**[DÉBUT DESCRIPTION IMAGE]**",
            "end_marker": "**[FIN DESCRIPTION IMAGE]**",
        },
        "es": {
            "section_heading": "## Descripciones de imágenes",
            "begin_marker": "**[INICIO DESCRIPCIÓN DE IMAGEN]**",
            "end_marker": "**[FIN DESCRIPCIÓN DE IMAGEN]**",
        },
        "it": {
            "section_heading": "## Descrizioni delle immagini",
            "begin_marker": "**[INIZIO DESCRIZIONE IMMAGINE]**",
            "end_marker": "**[FINE DESCRIZIONE IMMAGINE]**",
        },
        "pt": {
            "section_heading": "## Descrições de imagens extraídas",
            "begin_marker": "**[INÍCIO DESCRIÇÃO DA IMAGEM]**",
            "end_marker": "**[FIM DESCRIÇÃO DA IMAGEM]**",
        },
        "nl": {
            "section_heading": "## Geëxtraheerde afbeeldingsbeschrijvingen",
            "begin_marker": "**[BEGIN AFBEELDINGBESCHRIJVING]**",
            "end_marker": "**[EINDE AFBEELDINGBESCHRIJVING]**",
        },
        "pl": {
            "section_heading": "## Opisy wyodrębnionych obrazów",
            "begin_marker": "**[POCZĄTEK OPISU OBRAZU]**",
            "end_marker": "**[KONIEC OPISU OBRAZU]**",
        },
        "cs": {
            "section_heading": "## Popisy extrahovaných obrázků",
            "begin_marker": "**[ZAČÁTEK POPISU OBRÁZKU]**",
            "end_marker": "**[KONEC POPISU OBRÁZKU]**",
        },
        "ru": {
            "section_heading": "## Описания извлечённых изображений",
            "begin_marker": "**[НАЧАЛО ОПИСАНИЯ ИЗОБРАЖЕНИЯ]**",
            "end_marker": "**[КОНЕЦ ОПИСАНИЯ ИЗОБРАЖЕНИЯ]**",
        },
    }

    @classmethod
    def infer_output_language(cls, text: str) -> str:
        """
        Infers the language of the provided text sample.
        Uses a sample for performance.
        Defaults to 'en' if detection fails or signal is weak.
        """
        if not text or len(text.strip()) < 50:
            return "en"

        sample = text[:GlobalConfig.LANGUAGE_DETECTION_SAMPLE_SIZE]
        try:
            lang = detect(sample)
            if lang in cls._LANGUAGE_NAME_MAP:
                return lang
        except LangDetectException:
            logger.debug("Language detection failed; falling back to 'en'.", exc_info=True)

        return "en"

    @classmethod
    def resolve_language_name(cls, lang_code: str) -> str:
        """
        Maps ISO language code to human-readable name.
        """
        return cls._LANGUAGE_NAME_MAP.get(lang_code, "English")

    @classmethod
    def resolve_image_description_labels(cls, lang_code: str, app_config: GlobalConfig) -> Dict[str, str]:
        """
        Resolves localized labels for image descriptions based on language code.
        Falls back to global config defaults (which are English) if no localization is available.
        """
        labels = cls._LOCALIZED_LABELS.get(lang_code, {})
        return {
            "section_heading": labels.get("section_heading", app_config.image_description_section_heading),
            "begin_marker": labels.get("begin_marker", app_config.image_description_heading),
            "end_marker": labels.get("end_marker", app_config.image_description_end),
        }

class TextProcessor:
    """
    A utility class for processing text inputs, primarily for parsing configuration values.
    """
    @staticmethod
    def to_bool(value: Any) -> bool:
        """
        Parses various input types into a boolean value.

        Args:
            value (Any): The value to parse (str, int, float, or bool).

        Returns:
            bool: The parsed boolean value.

        Raises:
            TypeError: If the input value is not a string, number, or boolean.
            ValueError: If the string/number cannot be unambiguously parsed as a boolean.
        """
        if isinstance(value, bool):
            return value
        if value is None:
            return False

        if not isinstance(value, (str, int, float)):
            raise TypeError(f"Value '{value}' must be string or number, not {type(value)}")

        normalized_value = str(value).lower().strip()
        if not normalized_value:
            return False

        truthy_values = {'true', '1', 'yes', 'on'}
        falsy_values = {'false', '0', 'no', 'off'}

        if normalized_value in truthy_values:
            return True
        if normalized_value in falsy_values:
            return False

        raise ValueError(f"Value '{value}' is not parsable as a boolean.")

class ImageTokenCalculator:
    """
    Handles image token calculations based on configurable model settings.

    This class provides functionality for loading pre-trained model configurations and tokenizers,
    resolving model paths, and calculating the number of image tokens based on vision parameters such
    as patch size and spatial merge size. Defaults are applied conservatively in the absence of
    specific configuration values.

    :type model_path: Optional[str]
    :ivar config: Loaded model configuration used to extract vision parameters.
    :type config: Optional[transformers.AutoConfig]
    :ivar tokenizer: Loaded tokenizer for the model, if available.
    :type tokenizer: Optional[transformers.AutoTokenizer]
    :ivar effective_patch: Effective patch area calculated as patch_size * merge_size.
    :type effective_patch: int
    """
    def __init__(self, model_path: Optional[str] = None, model_name: Optional[str] = None):
        """
        :param model_path: Path to the local HF cache/directory.
        """
        if model_path is None and model_name is None:
            raise ValueError("Either model_path or model_name must be provided.")

        model_path_specified: str = model_path or self._resolve_model_path(model_name)

        # 1. Offline Loading Logic
        # local_files_only=True prevents any network attempts even if HF_HUB_OFFLINE is missed.
        try:
            self.config = AutoConfig.from_pretrained(
                model_path_specified,
                trust_remote_code=True,
                local_files_only=True
            )
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_path_specified,
                trust_remote_code=True,
                local_files_only=True
            )
        except Exception as e:
            print(f"Warning: Could not load config/tokenizer from {model_path}. Error: {e}")
            self.config = None
            self.tokenizer = None

        # 2. Get effective patch size
        self.effective_patch = self._get_effective_patch()

    @staticmethod
    def _resolve_model_path(model_name: str) -> str:
        """
        Resolves a model name to its local snapshot path using HF_HOME.
        Returns the path if found, otherwise returns the original model_name.
        """
        # This checks the cache for the model and returns the path to the config file
        filepath = try_to_load_from_cache(repo_id=model_name, filename="config.json")

        if filepath is not None and filepath is not _CACHED_NO_EXIST:
            # filepath is usually: .../snapshots/<hash>/config.json
            # We want the directory: .../snapshots/<hash>/
            return os.path.dirname(os.path.abspath(filepath))
        else:
            logger.debug(f"Model path for model {model_name} not found in cache. Try to work with the model name only")

        # If not found in the cache, return the name and hope AutoConfig finds it
        # via environment variables (HF_HOME/HF_HUB_OFFLINE)
        return model_name


    def _get_effective_patch(self) -> int:
        """
        Extracts vision parameters. If missing, defaults to Qwen2-VL specs
        to ensure a conservative (higher) token count.
        """
        # Default fallbacks (Conservative: smaller patch = more tokens)
        default_patch = 14
        default_merge = 1

        if not self.config:
            return default_patch * default_merge

        # Handle different config structures (vision_config vs top-level)

        try:
            vision_cfg = getattr(self.config, "vision_config")
        except AttributeError:
            logger.warning(f"No vision_config found in {self.config}. "
                           f"Using directly top-level config to extract patch_size and spatial_merge_size.")
            vision_cfg = self.config

        try:
            patch = getattr(vision_cfg, "patch_size")
        except AttributeError:
            logger.warning(f"No patch_size found in {self.config}. Using default: {default_patch}.")
            patch = default_patch

        try:
            merge = getattr(vision_cfg, "spatial_merge_size")
        except AttributeError:
            logger.warning(f"No spatial_merge_size found in {self.config}. Using default: {default_merge}.")
            merge = default_merge

        return patch * merge

    def calculate_image_tokens(self, image_source: Union[str, Path, Image.Image]) -> int:
        """Calculates image tokens based on spatial grid patches."""
        if isinstance(image_source, (str, Path)):
            with Image.open(image_source) as img:
                w, h = img.size
        else:
            w, h = image_source.size

        # Grid calculation: rounding up ensures we don't underestimate
        grid_w = math.ceil(w / self.effective_patch)
        grid_h = math.ceil(h / self.effective_patch)

        # Formula includes spatial tokens + newline tokens + overhead
        # Max tokens = (W_patches * H_patches) + H_patches + 4
        image_tokens = (grid_w * grid_h) + grid_h + 4
        return image_tokens
