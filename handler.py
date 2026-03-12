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

import runpod
import os
import subprocess
import requests
import json
import time
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser
from marker.output import text_from_rendered

ALLOWED_INPUT_FILE_EXTENSIONS = {'.pdf', '.pptx', '.docx', '.xlsx', '.html', '.epub'}
VALID_OUTPUT_FORMATS = {"json", "markdown", "html", "chunks"}
# Cache for marker models (surya, etc) to avoid reloading on every request
ARTIFACT_DICT = None


def check_and_pull_model(model_name):
    """
    Checks if the specified Ollama model exists locally.
    If not, pulls it from the registry.

    Args:
        model_name (str): The name of the Ollama model to check.

    Returns:
        bool: True if the model exists or was successfully pulled.

    Raises:
        RuntimeError: If the model cannot be found or pulled.
    """
    print(f"Checking for model: {model_name}")
    host = "http://localhost:11434"

    # 1. Get ALL local models via the tags endpoint
    try:
        response = requests.get(f"{host}/api/tags")
        if response.status_code != 200:
            raise RuntimeError("Could not connect to Ollama server.")
        
        models = [m["name"] for m in response.json().get("models", [])]
    except requests.exceptions.RequestException:
         raise RuntimeError("Could not connect to Ollama server.")

    # 2. Check for exact match or base name match (e.g., 'name' matches 'name:latest')
    if model_name in models or any(m.startswith(f"{model_name}:") for m in models):
        print(f"Model '{model_name}' found locally.")
        # Do NOT run 'ollama pull' here for custom models
        return True

    # 3. If NOT found, only pull if it's an official model.
    # For custom models, you'd need to run 'ollama create' instead.
    print(f"Model '{model_name}' not found. Attempting to pull official manifest...")
    try:
        # Set a timeout (e.g., 10 minutes) to prevent hanging indefinitely
        subprocess.run(["ollama", "pull", model_name], check=True, timeout=600)
        return True
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Timeout while pulling model '{model_name}'.")
    except subprocess.CalledProcessError:
        raise RuntimeError(f"Model '{model_name}' is not local and could not be pulled from registry.")

def load_models():
    """Loads marker models into memory if not already loaded."""
    global ARTIFACT_DICT
    if ARTIFACT_DICT is None:
        print("Loading marker models into VRAM...")
        ARTIFACT_DICT = create_model_dict()

class TextProcessor:
    """
    A utility class for processing text inputs, primarily for parsing configuration values.
    """
    @staticmethod
    def is_allowed_type_for_parsing(value):
        """
        Checks if the value is a string, integer, or float.

        Args:
            value: The value to check.

        Raises:
            TypeError: If the value is not a string, integer, or float.
        """
        if not isinstance(value, (str, int, float)):
            raise TypeError("Value must be string or number")

    def to_bool(self, value):
        """
        Converts a value to a boolean.

        Args:
            value: The value to convert. Can be a boolean, string, or number.

        Returns:
            bool: The boolean representation of the value.

        Raises:
            ValueError: If the value cannot be parsed as a boolean.
            TypeError: If the value is not a supported type.
        """
        if isinstance(value, bool):
            return value
        
        if value is None:
            return False

        self.is_allowed_type_for_parsing(value)
        
        normalized_value = str(value).lower().strip()
        if not normalized_value:
            return False
        if normalized_value in ('true', '1', 'yes', 'on'):
             return True
        if normalized_value in ('false', '0', 'no', 'off'):
             return False
        raise ValueError(f"Value '{value}' is not parsable as a boolean.")

    def is_parseable_as_int(self, value):
        """
        Checks if a value can be parsed as an integer.

        Args:
            value: The value to check.

        Returns:
            bool: True if the value can be parsed as an integer.

        Raises:
            ValueError: If the value cannot be parsed as an integer.
            TypeError: If the value is not a supported type.
        """
        self.is_allowed_type_for_parsing(value)
        try:
            int(value)
            return True
        except (ValueError, TypeError):
            raise ValueError(f"Value '{value}' is not parsable as an integer.")

def check_is_dir(path: str):
    """
    Checks if the given path is a directory.

    Args:
        path (str): The path to check.

    Raises:
        NotADirectoryError: If the path is not a directory.
    """
    if not os.path.isdir(path):
        raise NotADirectoryError(f"Path '{path}' is not a directory.")

def check_is_not_file(path: str):
    """
    Checks if the given path is not a file.

    Args:
        path (str): The path to check.

    Raises:
        ValueError: If the path is a file.
    """
    if os.path.isfile(path):
        raise ValueError(f"Path '{path}' is a file.")

def check_no_subdirs(path: str):
    """
    Checks if the directory at the given path contains any subdirectories.
    Ignores hidden directories.

    Args:
        path (str): The path to the directory.

    Raises:
        ValueError: If the directory contains subdirectories.
    """
    subdir_count = sum(1 for entry in os.scandir(path) if entry.is_dir() and not entry.name.startswith('.'))

    if subdir_count > 0:
        raise ValueError(f"Path '{path}' contains subdirectories.")

def is_empty_dir(path: str) -> bool:
    """
    Checks if a directory is empty.
    Ignores hidden files and directories.

    Args:
        path (str): The path to the directory.

    Returns:
        bool: True if the directory is empty (or only contains hidden files), False otherwise.
    """
    p = Path(path)
    if not p.is_dir():
        return False
    # Check if there are any non-hidden files/dirs
    for item in p.iterdir():
        if not item.name.startswith('.'):
            return False
    return True

def check_is_empty_dir(path: str):
    """
    Checks if the directory at the given path is empty.

    Args:
        path (str): The path to the directory.

    Raises:
        ValueError: If the directory is not empty.
    """
    if os.path.exists(path) and not is_empty_dir(path):
        raise ValueError(f"Directory '{path}' is not empty.")

def process_single_file(file_path: Path, converter, output_base_path: str):
    """
    Processes a single file using the provided converter and saves the output.

    Args:
        file_path (Path): The path to the file to process.
        converter (PdfConverter): The initialized PdfConverter instance.
        output_base_path (str): The base directory for saving output files.

    Returns:
        bool: True if the file was processed successfully.

    Raises:
        Exception: If an error occurs during processing.
    """
    try:
        print(f"Converting {file_path.name}...")
        rendered = converter(str(file_path))
        full_text, out_meta, images = text_from_rendered(rendered)
        
        # Create a subfolder for this file's output (similar to marker CLI)
        fname = file_path.stem
        out_folder = Path(output_base_path) / fname
        out_folder.mkdir(parents=True, exist_ok=True)

        # Save Markdown
        with open(out_folder / f"{fname}.md", "w", encoding="utf-8") as f:
            f.write(full_text)

        # Save Metadata
        with open(out_folder / f"{fname}_meta.json", "w", encoding="utf-8") as f:
            json.dump(out_meta, f, indent=4)

        # Save Images
        for img_filename, img in images.items():
            img.save(out_folder / img_filename)

        print(f"Finished {file_path.name}")
        return True
    except Exception as e:
        print(f"Error processing {file_path.name}: {e}")
        raise e

def handler(job):
    """
    RunPod Serverless Handler.

    Processes input documents using 'marker-pdf', optionally using an Ollama LLM model.

    Args:
        job (dict): The job payload containing input configuration.

    Returns:
        dict: A dictionary containing the status and message of the operation.
    """

    # --- Configuration ---
    text_processor = TextProcessor()
    ollama_model=""

    # Ensure models are loaded (Warm Start)
    load_models()
    global ARTIFACT_DICT

    # Load job input
    job_input = job.get("input", {})

    # Read environment variables
    storage_bucket_path = os.environ.get('VOLUME_ROOT_MOUNT_PATH')
    if not storage_bucket_path:
         raise ValueError("Environment variable VOLUME_ROOT_MOUNT_PATH is not set")

    use_postprocess_llm = text_processor.to_bool(os.environ.get('USE_POSTPROCESS_LLM'))
    cleanup_output_dir = text_processor.to_bool(os.environ.get('CLEANUP_OUTPUT_DIR_BEFORE_START'))

    # Get configuration from job input
    input_dir = job_input.get('input_dir')
    output_dir = job_input.get('output_dir')

    output_format = job_input.get('output_format', "markdown")
    if output_format not in VALID_OUTPUT_FORMATS:
        raise ValueError(f"output_format must be one of {VALID_OUTPUT_FORMATS}")

    if not input_dir or not output_dir:
        raise ValueError("input_dir and output_dir are required in job input")

    marker_workers = job_input.get('marker_workers')
    if marker_workers is not None:
        marker_workers = int(marker_workers)

    marker_block_correction_prompt = job_input.get("marker_block_correction_prompt", "")

    # Construct absolute paths
    # Handle case where input_dir might be a full path or relative
    if os.path.isabs(input_dir):
        input_path = input_dir
    else:
        input_path = os.path.join(storage_bucket_path, input_dir)

    if os.path.isabs(output_dir):
        output_path = output_dir
    else:
        output_path = os.path.join(storage_bucket_path, output_dir)

    # Check that input and output paths are actually directories
    check_is_dir(input_path)
    # Check that input path directory is actually flat, i.e. has no subdirectories
    check_no_subdirs(input_path)
    # Check that input dir is not empty
    if is_empty_dir(input_path):
        return {
            "status": "success",
            "message": "No files found to process."
        }

    check_is_not_file(output_path)
    # Only verify empty output dir if cleanup is disabled
    if not cleanup_output_dir:
        check_is_empty_dir(output_path)
    else:
        if os.path.exists(output_path):
            print(f"Cleaning output directory: {output_path}")
            shutil.rmtree(output_path)

    # Create output directory if not existent
    os.makedirs(output_path, exist_ok=True)

    # --- 2. Configure Marker ---
    # Map inputs to marker configuration dictionary
    marker_config = {
        "output_format": output_format,
        "output_dir": output_path,
        "debug": text_processor.to_bool(os.environ.get('MARKER_DEBUG', "false")),
        "paginate_output": text_processor.to_bool(job_input.get('marker_paginate_output', "false")),
        "force_ocr": text_processor.to_bool(job_input.get('marker_force_ocr', "false")),
        "disable_multiprocessing": text_processor.to_bool(job_input.get('marker_disable_multiprocessing', "false")),
        "disable_image_extraction": text_processor.to_bool(job_input.get('marker_disable_image_extraction', "false")),
        "page_range": job_input.get('marker_page_range'),
        "processors": job_input.get('marker_processors')
    }

    # Debug not typically used in library config directly same as CLI, but usually handled by logger
    # if marker_debug: ...

    if use_postprocess_llm:
        marker_config["use_llm"] = True
        marker_config["llm_service"] = "marker.services.ollama.OllamaService"
        ollama_model = os.environ.get('OLLAMA_MODEL')
        if not ollama_model:
            raise ValueError("Environment variable OLLAMA_MODEL is not set")
        if not check_and_pull_model(ollama_model):
            return {"error": f"Failed to pull or verify model: {ollama_model}"}
        marker_config["ollama_model"] = ollama_model
        marker_config["ollama_base_url"] = "http://localhost:11434" # Default for local
        if marker_block_correction_prompt:
            marker_config["block_correction_prompt"] = marker_block_correction_prompt

    # Initialize ConfigParser and Converter
    config_parser = ConfigParser(marker_config)
    
    converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=ARTIFACT_DICT,
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service() if use_postprocess_llm else None
    )

    print(f"--- Processing Job ---")
    print(f"Input Path: {input_path}")
    print(f"Output Path: {output_path}")
    if ollama_model:
        print(f"Ollama Model: {ollama_model}")
    
    # Collect files to process
    files_to_process = []
    # Note: input_path is guaranteed to be a directory by check_is_dir above
    for file in Path(input_path).iterdir():
        if file.is_file():
            if file.name.startswith('.'):
                continue
            if file.suffix.lower() in ALLOWED_INPUT_FILE_EXTENSIONS:
                files_to_process.append(file)
            else:
                print(f"Skipping unsupported file: {file.name}")

    if not files_to_process:
        return {
            "status": "success",
            "message": "No supported files found to process."
        }

    # --- 3. Execute Processing ---
    print(f"Starting conversion for {len(files_to_process)} files...")
    start_time = time.time()

    try:
        # Use ThreadPoolExecutor for parallelism if marker_workers is set > 1
        # Since models are on GPU, threading allows concurrent CPU pre/post processing
        # while sharing the single GPU model instance.
        max_workers = marker_workers if marker_workers and marker_workers > 1 else 1
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(process_single_file, file_to_process, converter, output_path)
                for file_to_process in files_to_process
            ]
            # Wait for all to complete and check for exceptions
            for future in futures:
                future.result()

        end_time = time.time()
        print(f"Marker execution took: {end_time - start_time:.2f} seconds")

    except Exception as e:
        print(f"Unexpected error occurred during marker processing: {e}")
        raise
    print(f"Marker Processing completed")

    # Cleanup: Delete original file on success
    for file_to_process in files_to_process:
        try:
            file_to_process.unlink()
        except Exception as e:
            print(f"Warning: Failed to delete input file {file_to_process}: {e}")

    return {
        "status": "completed",
        "message": f"All input files of {input_path} processed."
    }

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
