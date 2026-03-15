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
Main handler for the marker-ollama-worker.
Orchestrates the conversion of documents using the marker-pdf library and
optional post-processing using an Ollama-powered LLM.
"""

import atexit
import gc
import logging
import runpod
import os
import shutil
import time
import json
import sys
import torch
import torch.multiprocessing as mp
import re
from pathlib import Path
from typing import Optional, Any, Dict, Tuple, Set, List

# Ensure threads don't contend - important for multiprocessing
os.environ["MKL_DYNAMIC"] = "FALSE"
os.environ["OMP_DYNAMIC"] = "FALSE"
os.environ["OMP_NUM_THREADS"] = "2"  # Avoid OpenMP issues with multiprocessing
os.environ["OPENBLAS_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"  # Transformers uses .isin for a simple op, which is not supported on MPS
os.environ["IN_STREAMLIT"] = "true"  # Avoid multiprocessing inside surya

# Set multiprocessing start method early (required for CUDA)
try:
    mp.set_start_method("spawn", force=True)
except RuntimeError:
    # Already set, which is fine
    pass

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser
from marker.output import text_from_rendered
from ollama_worker import OllamaWorker
from settings import GlobalConfig, MarkerSettings, OllamaSettings
from utils import (
    check_is_dir,
    check_is_not_file,
    check_no_subdirs,
    is_empty_dir,
    check_is_empty_dir,
    setup_config,
    log_vram_usage
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

ALLOWED_INPUT_FILE_EXTENSIONS: Set[str] = {'.pdf', '.pptx', '.docx', '.xlsx', '.html', '.epub'}
VALID_OUTPUT_FORMATS: Set[str] = {"json", "markdown", "html", "chunks"}
FORMAT_EXTENSIONS: Dict[str, str] = {
    "markdown": ".md",
    "json": ".json",
    "html": ".html",
    "chunks": ".txt"
}
UTF8_ENCODING: str = "utf-8"
IMAGE_FILE_EXTENSIONS: Set[str] = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
TEXT_OUTPUT_FILE_EXTENSIONS: Set[str] = {".md", ".txt"}
IMAGE_DESCRIPTION_SECTION_HEADING: str = "## Extracted Image Descriptions"
VRAM_RESERVE_GB: int = 4
OLLAMA_VRAM_PER_TOKEN_FACTOR: float = 0.00013
OLLAMA_CONTEXT_LENGTH: int = int(os.environ.get("OLLAMA_CONTEXT_LENGTH", "4096"))
# Block correction prompt library (loaded from JSON)
BLOCK_CORRECTION_PROMPT_LIBRARY: Dict[str, str] = {}

# Global application configuration (loaded once)
_APP_CONFIG: Optional[GlobalConfig] = None

# Process-local marker models (each worker process has its own copy)
_MARKER_MODELS: Optional[Dict[str, Any]] = None


def marker_worker_init() -> None:
    """
    Initializes marker models for each worker process.
    This function is called once per worker process when the pool is created.
    Models are loaded into VRAM and stored in process-local _MARKER_MODELS variable.
    """
    global _MARKER_MODELS
    logger.info(f"Worker process {os.getpid()} initializing marker models...")
    _MARKER_MODELS = create_model_dict()

    # Register cleanup on exit
    atexit.register(marker_worker_exit)
    logger.info(f"Worker process {os.getpid()} ready")


def marker_worker_exit() -> None:
    """
    Cleanup function for worker processes.
    Releases marker models and clears CUDA cache when a worker process exits.
    """
    global _MARKER_MODELS
    try:
        if _MARKER_MODELS:
            del _MARKER_MODELS
            torch.cuda.empty_cache()
            gc.collect()
    except Exception as e:
        logger.debug(f"Error during worker cleanup: {e}")

def load_block_correction_prompts() -> None:
    """
    Loads the block correction prompt library from a JSON file located in the same directory.
    The prompts are stored in the global BLOCK_CORRECTION_PROMPT_LIBRARY dictionary.
    """
    global BLOCK_CORRECTION_PROMPT_LIBRARY
    if BLOCK_CORRECTION_PROMPT_LIBRARY:
        return  # Already loaded

    prompt_file = Path(__file__).parent / "block_correction_prompts.json"

    try:
        if not prompt_file.exists():
            logger.warning(f"Block correction prompt file not found: {prompt_file}")
            return

        with open(prompt_file, 'r', encoding='UTF8_ENCODING') as f:
            data = json.load(f)

        # Build dictionary: key -> prompt
        for entry in data.get("prompts", []):
            key = entry.get("key")
            prompt = entry.get("prompt")
            if key and prompt:
                BLOCK_CORRECTION_PROMPT_LIBRARY[key] = prompt

        logger.info(f"Loaded {len(BLOCK_CORRECTION_PROMPT_LIBRARY)} block correction prompts from catalog")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse block correction prompts JSON: {e}")
    except Exception as e:
        logger.error(f"Failed to load block correction prompts: {e}")

def calculate_optimal_workers(
    num_files: int,
    use_postprocess_llm: bool,
    marker_workers_override: Optional[int] = None
) -> Tuple[int, int, int]:
    """
    Calculates optimal worker counts based on workload and available VRAM.

    Args:
        num_files (int): Number of files to process
        use_postprocess_llm (bool): Whether LLM post-processing will be used
        marker_workers_override (Optional[int]): Manual override for marker workers

    Returns:
        tuple: (marker_workers, ollama_chunk_workers, ollama_num_parallel)
    """
    # Get VRAM configuration
    total_vram = int(os.environ.get("TOTAL_VRAM_GB", "24"))
    marker_vram_per_worker = int(os.environ.get("MARKER_VRAM_PER_WORKER", "5"))

    # Parse marker_workers
    if marker_workers_override is not None:
        marker_workers = max(1, marker_workers_override)
    else:
        # Linear/Consistent scaling for marker workers
        marker_workers = min(4, num_files, (total_vram - VRAM_RESERVE_GB) // marker_vram_per_worker)

    marker_workers = max(1, marker_workers)

    # Calculate ollama_chunk_workers hint
    # We account for both the base model VRAM usage and per-worker context usage.
    ollama_num_parallel = 1
    if not use_postprocess_llm:
        ollama_chunk_workers = 1
    else:
        # Use environment variables or calculate based on VRAM
        # Base reserve for the model weights themselves (default 8GB)
        ollama_base_vram = int(os.environ.get("OLLAMA_BASE_VRAM_GB", "8"))
        # VRAM factor (default 0.00013 GB per token)
        ollama_vram_factor = float(os.environ.get("OLLAMA_VRAM_FACTOR") or OLLAMA_VRAM_PER_TOKEN_FACTOR)

        # Calculate how many parallel contexts fit in remaining VRAM
        # Note: marker models are on CPU during Ollama phase, so we don't subtract them
        available_ollama_vram = total_vram - VRAM_RESERVE_GB - ollama_base_vram

        context_vram_gb = ollama_vram_factor * OLLAMA_CONTEXT_LENGTH

        if available_ollama_vram <= 0:
            ollama_num_parallel = 1
        else:
            ollama_num_parallel = max(1, int(available_ollama_vram // context_vram_gb))

        # ollama_chunk_workers (Python threads) should be decoupled and saturated
        # We can set a higher default to ensure the Ollama queue is always full.
        # Default to 16, but respect existing user overrides if they come later.
        ollama_chunk_workers = 16

    logger.info(f"Calculated optimal workers for {num_files} files: "
                f"marker={marker_workers}, ollama_chunk_threads={ollama_chunk_workers}, "
                f"ollama_num_parallel={ollama_num_parallel}")

    return marker_workers, ollama_chunk_workers, ollama_num_parallel

def list_extracted_images_for_output_file(output_file_path: Path) -> List[Path]:
    """
    Lists extracted image files located next to a marker output file.

    Args:
        output_file_path (Path): Path to the marker output text file.

    Returns:
        List[Path]: Sorted image paths found in the same output directory.
    """
    output_dir = output_file_path.parent
    if not output_dir.exists() or not output_dir.is_dir():
        return []

    return sorted(
        [
            path for path in output_dir.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_FILE_EXTENSIONS
        ],
        key=lambda path: path.name.lower()
    )

def insert_image_descriptions_to_text_file(
    output_file_path: Path,
    image_descriptions: List[Tuple[Path, str]]
) -> bool:
    """
    Inserts generated image descriptions into a text output file at the position
    where the image appears, or appends them to the end if the position cannot be found.

    Args:
        output_file_path (Path): Marker output text file.
        image_descriptions (List[Tuple[Path, str]]): (image path, description) tuples.

    Returns:
        bool: True when descriptions were inserted or appended, False otherwise.
    """
    if output_file_path.suffix.lower() not in TEXT_OUTPUT_FILE_EXTENSIONS:
        logger.info(f"Skipping image description insertion for non-text output file: {output_file_path.name}")
        return False

    if not image_descriptions:
        return False

    valid_descriptions = [
        (image_path, description.strip())
        for image_path, description in image_descriptions
        if description and description.strip()
    ]
    if not valid_descriptions:
        return False

    if not output_file_path.exists():
        logger.warning(f"Cannot insert image descriptions because output file is missing: {output_file_path}")
        return False

    original_text = output_file_path.read_text(encoding=UTF8_ENCODING)
    modified_text = original_text
    unplaced_descriptions = []

    # Try to insert each description after its corresponding image tag
    for image_path, description in valid_descriptions:
        filename = image_path.name
        # Escape filename for regex
        escaped_filename = re.escape(filename)

        # Pattern for Markdown: ![alt text](path/to/image.png)
        # We look for the filename in the path part of the Markdown image tag.
        # This handles absolute paths, relative paths, and optional query parameters.
        pattern = rf'!\[.*?\]\((?:.*?[/\\])?{escaped_filename}(?:\?.*?)?\)'

        if re.search(pattern, modified_text):
            # Insertion format: immediately after the tag, with a newline.
            # We use a blockquote with explicit start/end markers for LLM clarity.
            indented_description = description.replace("\n", "\n> ")
            insertion = (
                f"\n\n> **[BEGIN IMAGE DESCRIPTION]**"
                f"\n> {indented_description}"
                f"\n> **[END IMAGE DESCRIPTION]**\n"
            )
            modified_text = re.sub(pattern, rf'\g<0>{insertion}', modified_text, count=1)
        else:
            unplaced_descriptions.append((image_path, description))

    # Fallback: append unplaced descriptions at the end
    if unplaced_descriptions:
        section_lines = ["", IMAGE_DESCRIPTION_SECTION_HEADING, ""]
        for image_path, description in unplaced_descriptions:
            section_lines.append(f"### Image: `{image_path.name}`")
            section_lines.append("**[BEGIN IMAGE DESCRIPTION]**")
            section_lines.append(description)
            section_lines.append("**[END IMAGE DESCRIPTION]**")
            section_lines.append("")

        section_text = "\n".join(section_lines).strip()
        modified_text = f"{modified_text.rstrip()}\n\n{section_text}\n"

    if modified_text != original_text:
        output_file_path.write_text(modified_text, encoding=UTF8_ENCODING)
        return True

    return False

def _save_marker_output(
    out_folder: Path,
    file_stem: str,
    full_text: str,
    out_meta: Dict[str, Any],
    images: Dict[str, Any],
    output_format: str
) -> Path:
    """
    Saves the converted content (text, metadata, images) to the output folder.

    Args:
        out_folder (Path): The directory where output files will be saved.
        file_stem (str): The filename without extension.
        full_text (str): The extracted text from the document.
        out_meta (Dict[str, Any]): Metadata from the conversion process.
        images (Dict[str, Any]): Dictionary of image names and image objects.
        output_format (str): The desired output format (e.g., 'markdown', 'json').

    Returns:
        Path: The path to the main output file.
    """

    extension = FORMAT_EXTENSIONS[output_format]
    output_file = out_folder / f"{file_stem}{extension}"

    # Save output in the specified format
    output_file.write_text(full_text, encoding=UTF8_ENCODING)

    # Save Metadata
    meta_file = out_folder / f"{file_stem}_meta.json"
    meta_file.write_text(json.dumps(out_meta, indent=4), encoding=UTF8_ENCODING)

    # Save Images
    for img_filename, img in images.items():
        img.save(out_folder / img_filename)

    return output_file

def marker_process_single_file(
    file_path: Path,
    marker_config: Dict[str, Any],
    output_base_path: Path,
    output_format: str
) -> Tuple[bool, Optional[Path]]:
    """
    Processes a single file using the provided converter and saves the output.
    Uses process-local marker models loaded during worker initialization.

    Args:
        file_path (Path): Path to the input file (e.g., .pdf, .docx).
        marker_config (Dict[str, Any]): Configuration for the marker converter.
        output_base_path (Path): The root directory where output for this file will be saved.
        output_format (str): The desired output format (e.g., 'markdown', 'json').

    Returns:
        Tuple[bool, Optional[Path]]: A tuple containing (success_boolean, output_file_path).
    """
    global _MARKER_MODELS
    try:
        logger.info(f"Converting {file_path.name}...")

        # Initialize converter using process-local models
        config_parser = ConfigParser(marker_config)
        converter = PdfConverter(
            config=config_parser.generate_config_dict(),
            artifact_dict=_MARKER_MODELS,
            processor_list=config_parser.get_processors(),
            renderer=config_parser.get_renderer(),
            llm_service=None  # No internal LLM service
        )

        rendered = converter(str(file_path))
        full_text, out_meta, images = text_from_rendered(rendered)

        # Create a subfolder for this file's output
        file_stem = file_path.stem
        out_folder = Path(output_base_path) / file_stem
        out_folder.mkdir(parents=True, exist_ok=True)

        # Save output files
        output_file = _save_marker_output(
            out_folder,
            file_stem,
            full_text,
            out_meta,
            images,
            output_format
        )

        logger.info(f"Finished {file_path.name}")
        return True, output_file
    except Exception as e:
        logger.error(f"Error processing {file_path.name}: {e}")
        # Return False and None to allow other files in the pool to continue
        return False, None

def extract_ollama_settings_from_job_input(job_input: Dict[str, Any]) -> OllamaSettings:
    """
    Extracts and validates OllamaSettings from job input.
    """
    ollama_input = {
        k[len("ollama_"):]: v
        for k, v in job_input.items()
        if k.startswith("ollama_")
    }
    return OllamaSettings(**ollama_input)

def extract_marker_settings_from_job_input(job_input: Dict[str, Any]) -> MarkerSettings:
    """
    Extracts and validates MarkerSettings from job input.
    """
    marker_input = {
        k[len("marker_"):]: v
        for k, v in job_input.items()
        if k.startswith("marker_")
    }
    # Add shared parameters
    marker_input["output_format"] = job_input.get("output_format", "markdown")
    return MarkerSettings(**marker_input)

def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    RunPod Serverless Handler.
    Processes input documents using 'marker-pdf', optionally using an Ollama LLM model.
    """
    global _APP_CONFIG

    # --- Configuration and Environment Setup ---
    if not _APP_CONFIG:
        _APP_CONFIG = setup_config()

    log_vram_usage("Start")

    # Load job input
    job_input = job.get("input", {})

    # Extract structured settings
    ollama_settings = extract_ollama_settings_from_job_input(job_input)
    marker_settings = extract_marker_settings_from_job_input(job_input)

    # --- 1. Ollama Model Setup (Pre-processing) ---
    if _APP_CONFIG.use_postprocess_llm:
        ollama_worker = OllamaWorker(settings=ollama_settings)
        ollama_worker.initialize_model()
        torch.cuda.empty_cache()
        log_vram_usage("After initialize_model")

    # Read base paths from global config
    storage_bucket_path = _APP_CONFIG.volume_root_mount_path
    cleanup_output_dir = _APP_CONFIG.cleanup_output_dir_before_start

    # Get job-specific configuration
    input_dir = job_input.get('input_dir')
    output_dir = job_input.get('output_dir')
    output_format = marker_settings.output_format

    if output_format not in VALID_OUTPUT_FORMATS:
        raise ValueError(f"output_format must be one of {VALID_OUTPUT_FORMATS}")

    if not input_dir or not output_dir:
        raise ValueError("input_dir and output_dir are required in job input")

    delete_input_on_success = bool(job_input.get('delete_input_on_success', False))

    # Resolve block correction prompt (priority: direct prompt > prompt key > empty)
    ollama_block_correction_prompt = job_input.get("ollama_block_correction_prompt")
    if not ollama_block_correction_prompt:
        # Try to look up by key if direct prompt not provided
        block_correction_prompt_key = job_input.get("block_correction_prompt_key")
        if block_correction_prompt_key:
            if block_correction_prompt_key in BLOCK_CORRECTION_PROMPT_LIBRARY:
                ollama_block_correction_prompt = BLOCK_CORRECTION_PROMPT_LIBRARY[block_correction_prompt_key]
                logger.info(f"Using block correction prompt from catalog: '{block_correction_prompt_key}'")
            else:
                logger.warning(f"Block correction prompt key '{block_correction_prompt_key}' not found in catalog. Available keys: {list(BLOCK_CORRECTION_PROMPT_LIBRARY.keys())}")
    else:
        logger.info("Using custom block correction prompt provided in job input")

    # Construct absolute paths
    if os.path.isabs(input_dir):
        input_path = Path(input_dir)
    else:
        input_path = storage_bucket_path / input_dir

    if os.path.isabs(output_dir):
        output_path = Path(output_dir)
    else:
        output_path = storage_bucket_path / output_dir

    # Validate paths
    check_is_dir(input_path)
    check_no_subdirs(input_path)
    if is_empty_dir(input_path):
        return {"status": "success", "message": "No files found to process."}

    check_is_not_file(output_path)
    if not cleanup_output_dir:
        check_is_empty_dir(output_path)
    else:
        if os.path.exists(output_path):
            logger.info(f"Cleaning output directory: {output_path}")
            shutil.rmtree(output_path)

    os.makedirs(output_path, exist_ok=True)

    # --- Configure Marker (Without internal LLM) ---
    marker_config = {
        "output_format": marker_settings.output_format,
        "output_dir": output_path,
        "debug": bool(os.environ.get('MARKER_DEBUG', "false").lower() == "true"),
        "paginate_output": marker_settings.paginate_output,
        "force_ocr": marker_settings.force_ocr,
        "disable_multiprocessing": marker_settings.disable_multiprocessing,
        "disable_image_extraction": marker_settings.disable_image_extraction,
        "page_range": marker_settings.page_range,
        "processors": marker_settings.processors,
        "use_llm": False # Explicitly disable Marker's internal LLM logic
    }

    logger.info("--- Processing Job ---")
    logger.info(f"Input Path: {input_path}")
    logger.info(f"Output Path: {output_path}")

    files_to_process = []
    for file in Path(input_path).iterdir():
        if file.is_file():
            if file.name.startswith('.'):
                continue
            if file.suffix.lower() in ALLOWED_INPUT_FILE_EXTENSIONS:
                files_to_process.append(file)
            else:
                logger.warning(f"Skipping unsupported file: {file.name}")

    if not files_to_process:
        return {"status": "success", "message": "No supported files found to process."}

    # --- Calculate optimal worker counts ---
    optimal_marker_workers, ollama_chunk_workers, ollama_num_parallel = calculate_optimal_workers(
        num_files=len(files_to_process),
        use_postprocess_llm=_APP_CONFIG.use_postprocess_llm,
        marker_workers_override=marker_settings.workers
    )

    # Get job-level override for ollama chunk workers
    ollama_chunk_workers_override = job_input.get('ollama_chunk_workers')
    if ollama_chunk_workers_override is not None:
        ollama_chunk_workers = int(ollama_chunk_workers_override)
        logger.info(f"Using job-level override for ollama_chunk_workers (threads): {ollama_chunk_workers}")

    # --- Execute Marker Processing ---
    logger.info(f"Starting conversion for {len(files_to_process)} files...")
    start_time = time.time()
    processed_files = [] # Paths of successfully processed output files
    successful_inputs = [] # Original paths of successfully processed files

    try:
        # Prepare arguments for each file
        task_args = [
            (file_to_process, marker_config, output_path, output_format)
            for file_to_process in files_to_process
        ]

        # Use multiprocessing Pool with worker initialization
        with mp.Pool(
            processes=optimal_marker_workers,
            initializer=marker_worker_init,
            maxtasksperchild=10  # Recycle workers periodically to free VRAM
        ) as pool:
            # Process files and collect results
            results = pool.starmap(marker_process_single_file, task_args)

            # Separate successful results from failed ones
            for idx, (success, output_file_path) in enumerate(results):
                if success and output_file_path:
                    processed_files.append(output_file_path)
                    successful_inputs.append(files_to_process[idx])

        end_time = time.time()
        logger.info(f"Marker execution took: {end_time - start_time:.2f} seconds")
        torch.cuda.empty_cache()
        log_vram_usage("After Marker")

    except Exception as e:
        logger.error(f"Unexpected error occurred during marker processing: {e}")
        # If marker fails critically, we abort
        raise

    logger.info("Marker Processing completed")

    # --- 3. Ollama LLM Post-processing (Parallel) ---
    if _APP_CONFIG.use_postprocess_llm and processed_files:
        # Note: Marker worker processes have terminated, releasing their VRAM
        # Ollama now has full access to VRAM
        log_vram_usage("Before starting Ollama server")

        logger.info("--- Starting Ollama for Post-processing ---")

        # Set Ollama parallelism based on calculated values if not explicitly overridden
        if ollama_settings.num_parallel is None:
            ollama_settings.num_parallel = ollama_num_parallel
            logger.info(f"Setting Ollama num_parallel={ollama_num_parallel} based on VRAM/Context calculation")

        ollama_worker = None
        try:
            # Restart Ollama server
            # We recreate the worker instance with the same configuration
            ollama_worker = OllamaWorker(settings=ollama_settings)
            ollama_worker.start_server()

            # Note: Model should already be there from step 1, but ensure_model calls check_exists first
            # so it's inexpensive to call again to be sure.
            ollama_worker.ensure_model()

            logger.info(f"Post-processing {len(processed_files)} files sequentially with {ollama_chunk_workers} chunk workers...")

            # Process files sequentially, with parallel chunk processing within each file
            for processed_file_path in processed_files:
                ollama_worker.process_file(
                    file_path=processed_file_path,
                    prompt_template=ollama_block_correction_prompt,
                    max_chunk_workers=ollama_chunk_workers
                )

                extracted_images = list_extracted_images_for_output_file(processed_file_path)
                if not extracted_images:
                    continue

                image_descriptions = ollama_worker.describe_images(
                    image_paths=extracted_images,
                    prompt_template=ollama_settings.image_description_prompt,
                    max_image_workers=ollama_chunk_workers
                )

                inserted_descriptions = insert_image_descriptions_to_text_file(
                    output_file_path=processed_file_path,
                    image_descriptions=image_descriptions
                )
                if inserted_descriptions:
                    logger.info(
                        f"Inserted {len(image_descriptions)} image descriptions into {processed_file_path.name}"
                    )

            # Cleanup
            ollama_worker.unload_model()
            ollama_worker.stop_server()
            torch.cuda.empty_cache()
            log_vram_usage("Final")

        except Exception as e:
            logger.error(f"Error during Ollama post-processing phase: {e}")
            if ollama_worker:
                ollama_worker.stop_server()

    # Cleanup: Delete original file on success
    # Only delete if we reached here successfully and delete_input_on_success is enabled
    if delete_input_on_success:
        for file_to_process in successful_inputs:
            try:
                file_to_process.unlink()
                logger.info(f"Deleted input file: {file_to_process.name}")
            except Exception as e:
                logger.warning(f"Failed to delete input file {file_to_process}: {e}")

    return {
        "status": "completed",
        "message": f"All input files of {input_path} processed."
    }

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
