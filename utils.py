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

import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Union

from settings import GlobalConfig

logger = logging.getLogger(__name__)

def setup_config() -> GlobalConfig:
    """
    Validates and configures environment variables, and ensures required directories exist.

    This function:
    1. Instantiates GlobalConfig, which performs Pydantic validation of environment variables.
    2. Ensures that directories for Ollama models, logs, and Hugging Face cache exist.
    3. Sets environment variables for downstream libraries (Ollama, HF).
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

    # Ensure directories exist
    os.makedirs(config.ollama_models, exist_ok=True)
    os.makedirs(config.ollama_logs, exist_ok=True)
    os.makedirs(config.hf_home, exist_ok=True)

    # Set env vars for libraries that expect them (Ollama, Hugging Face)
    os.environ["OLLAMA_MODELS"] = str(config.ollama_models)
    os.environ["OLLAMA_LOGS"] = str(config.ollama_logs)
    os.environ["HF_HOME"] = str(config.hf_home)
    os.environ["USE_POSTPROCESS_LLM"] = str(config.use_postprocess_llm).lower()
    os.environ["CLEANUP_OUTPUT_DIR_BEFORE_START"] = str(config.cleanup_output_dir_before_start).lower()

    # Ownership/Permissions (if root)
    if os.getuid() == 0:
        _update_ownership(str(config.ollama_models), str(config.ollama_logs), str(config.hf_home))

    # OLLAMA_MODEL validation for post-processing
    if config.use_postprocess_llm:
        # Check if the model is provided in the environment. Note: job input overrides are handled in handler.py
        ollama_model = os.environ.get("OLLAMA_MODEL")
        if not ollama_model:
            hf_name = os.environ.get("OLLAMA_HUGGING_FACE_MODEL_NAME")
            hf_quant = os.environ.get("OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION")
            if not hf_name or not hf_quant:
                 raise ValueError(
                     "OLLAMA_HUGGING_FACE_MODEL_NAME and OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION "
                     "must be defined when OLLAMA_MODEL is not set and USE_POSTPROCESS_LLM is true"
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
                subprocess.run(["chmod", "-R", "777", path], stderr=subprocess.DEVNULL, check=False)
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
