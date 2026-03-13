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
import runpod
import os
import shutil
import time
import json
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Any, Dict, Tuple, Set

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser
from marker.output import text_from_rendered
from ollama_worker import OllamaWorker
from utils import (
    check_is_dir,
    check_is_not_file,
    check_no_subdirs,
    is_empty_dir,
    check_is_empty_dir,
    TextProcessor
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
VRAM_RESERVE_GB: int = 4
# Cache for marker models (surya, etc) to avoid reloading on every request
ARTIFACT_DICT: Optional[Dict[str, Any]] = None
# Block correction prompt library (loaded from JSON)
BLOCK_CORRECTION_PROMPT_LIBRARY: Dict[str, str] = {}

def load_models() -> None:
    """Loads marker models into memory if not already loaded."""
    global ARTIFACT_DICT
    if ARTIFACT_DICT is None:
        logger.info("Loading marker models into VRAM...")
        ARTIFACT_DICT = create_model_dict()

def load_block_correction_prompts() -> None:
    """Loads block correction prompt library from JSON file."""
    global BLOCK_CORRECTION_PROMPT_LIBRARY
    if BLOCK_CORRECTION_PROMPT_LIBRARY:
        return  # Already loaded

    prompt_file = Path(__file__).parent / "block_correction_prompts.json"

    try:
        if not prompt_file.exists():
            logger.warning(f"Block correction prompt file not found: {prompt_file}")
            return

        with open(prompt_file, 'r', encoding='utf-8') as f:
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
) -> Tuple[int, int]:
    """
    Calculates optimal worker counts based on workload and available VRAM.

    Args:
        num_files (int): Number of files to process
        use_postprocess_llm (bool): Whether LLM post-processing will be used
        marker_workers_override (Optional[int]): Manual override for marker workers

    Returns:
        tuple: (marker_workers, ollama_chunk_workers)
    """
    # Get VRAM configuration
    total_vram = int(os.environ.get("TOTAL_VRAM_GB", "24"))
    marker_vram_per_worker = int(os.environ.get("MARKER_VRAM_PER_WORKER", "5"))

    # Parse marker_workers
    if marker_workers_override is not None:
        marker_workers = max(1, marker_workers_override)
    # Auto-detection logic for marker workers
    elif num_files == 1:
        # Single file - use 1 marker worker
        marker_workers = 1
    elif num_files <= 3:
        # Small batch - moderate parallelism
        marker_workers = min(2, num_files, (total_vram - VRAM_RESERVE_GB) // marker_vram_per_worker)
    else:
        # Large batch - maximize marker parallelism
        marker_workers = min(4, num_files, (total_vram - VRAM_RESERVE_GB) // marker_vram_per_worker)

    marker_workers = max(1, marker_workers)

    # Calculate ollama_chunk_workers hint
    # Since we only parallelize at chunk level, we can be more aggressive
    if not use_postprocess_llm:
        ollama_chunk_workers = 1
    else:
        # Use environment variable or calculate based on VRAM
        ollama_vram_per_worker = int(os.environ.get("OLLAMA_VRAM_PER_WORKER", "5"))
        max_vram_workers = max(1, (total_vram - VRAM_RESERVE_GB) // ollama_vram_per_worker)

        # Cap at reasonable maximum
        ollama_chunk_workers = min(max_vram_workers, 4)

    logger.info(f"Calculated optimal workers for {num_files} files: "
                f"marker={marker_workers}, ollama_chunk={ollama_chunk_workers}")

    return marker_workers, ollama_chunk_workers

def marker_process_single_file(
    file_path: Path,
    converter: PdfConverter,
    output_base_path: str,
    output_format: str
) -> Tuple[bool, Path]:
    """
    Processes a single file using the provided converter and saves the output.
    """
    try:
        logger.info(f"Converting {file_path.name}...")
        rendered = converter(str(file_path))
        full_text, out_meta, images = text_from_rendered(rendered)

        # Create a subfolder for this file's output
        fname = file_path.stem
        out_folder = Path(output_base_path) / fname
        out_folder.mkdir(parents=True, exist_ok=True)

        # Determine file extension based on output format
        format_extensions = {
            "markdown": ".md",
            "json": ".json",
            "html": ".html",
            "chunks": ".txt"
        }
        extension = format_extensions.get(output_format, ".md")
        output_file = out_folder / f"{fname}{extension}"

        # Save output in the specified format
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(full_text)

        # Save Metadata
        with open(out_folder / f"{fname}_meta.json", "w", encoding="utf-8") as f:
            json.dump(out_meta, f, indent=4)

        # Save Images
        for img_filename, img in images.items():
            img.save(out_folder / img_filename)

        logger.info(f"Finished {file_path.name}")
        return True, output_file
    except Exception as e:
        logger.error(f"Error processing {file_path.name}: {e}")
        # Raise to propagate the failure
        raise e

def handler(job: Dict[str, Any]) -> Dict[str, str]:
    """
    RunPod Serverless Handler.
    Processes input documents using 'marker-pdf', optionally using an Ollama LLM model.
    """

    # --- Configuration ---
    text_processor = TextProcessor()

    # --- 1. Ollama Model Setup (Pre-processing) ---
    use_postprocess_llm = text_processor.to_bool(os.environ.get('USE_POSTPROCESS_LLM'))

    if use_postprocess_llm:
        ollama_worker = OllamaWorker()
        ollama_worker.initialize_model()

    # --- 2. Marker Processing ---

    # Ensure marker models are loaded (Warm Start)
    load_models()
    # Load block correction prompt catalog
    load_block_correction_prompts()
    global ARTIFACT_DICT

    # Load job input
    job_input = job.get("input", {})

    # Read environment variables
    storage_bucket_path = os.environ.get('VOLUME_ROOT_MOUNT_PATH')
    if not storage_bucket_path:
         raise ValueError("Environment variable VOLUME_ROOT_MOUNT_PATH is not set")

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

    # Resolve block correction prompt (priority: direct prompt > prompt key > empty)
    ollama_block_correction_prompt = job_input.get("ollama_block_correction_prompt", "")
    if not ollama_block_correction_prompt:
        # Try to lookup by key if direct prompt not provided
        block_correction_prompt_key = job_input.get("block_correction_prompt_key", "")
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
        input_path = input_dir
    else:
        input_path = os.path.join(storage_bucket_path, input_dir)

    if os.path.isabs(output_dir):
        output_path = output_dir
    else:
        output_path = os.path.join(storage_bucket_path, output_dir)

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
        "output_format": output_format,
        "output_dir": output_path,
        "debug": text_processor.to_bool(os.environ.get('MARKER_DEBUG', "false")),
        "paginate_output": text_processor.to_bool(job_input.get('marker_paginate_output', "false")),
        "force_ocr": text_processor.to_bool(job_input.get('marker_force_ocr', "false")),
        "disable_multiprocessing": text_processor.to_bool(job_input.get('marker_disable_multiprocessing', "false")),
        "disable_image_extraction": text_processor.to_bool(job_input.get('marker_disable_image_extraction', "false")),
        "page_range": job_input.get('marker_page_range'),
        "processors": job_input.get('marker_processors'),
        "use_llm": False # Explicitly disable Marker's internal LLM logic
    }

    # Initialize ConfigParser and Converter
    config_parser = ConfigParser(marker_config)

    converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=ARTIFACT_DICT,
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
        llm_service=None # No internal LLM service
    )

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
    optimal_marker_workers, ollama_chunk_workers = calculate_optimal_workers(
        num_files=len(files_to_process),
        use_postprocess_llm=use_postprocess_llm,
        marker_workers_override=marker_workers
    )

    # Get job-level override for ollama chunk workers
    ollama_chunk_workers_override = job_input.get('ollama_chunk_workers')
    if ollama_chunk_workers_override is not None:
        ollama_chunk_workers = int(ollama_chunk_workers_override)
        logger.info(f"Using job-level override for ollama_chunk_workers: {ollama_chunk_workers}")

    # --- Execute Marker Processing ---
    logger.info(f"Starting conversion for {len(files_to_process)} files...")
    start_time = time.time()
    processed_files = [] # Tuples of (original_path, output_file_path)
    successful_inputs = [] # Original paths of successfully processed files

    try:
        with ThreadPoolExecutor(max_workers=optimal_marker_workers) as executor:
            # Future mapping to file for error tracking if needed
            future_to_file = {
                executor.submit(marker_process_single_file, file_to_process, converter, output_path, output_format): file_to_process
                for file_to_process in files_to_process
            }

            for future in as_completed(future_to_file):
                input_file = future_to_file[future]
                try:
                    success, output_file_path = future.result()
                    if success:
                        processed_files.append(output_file_path)
                        successful_inputs.append(input_file)
                except Exception as e:
                    logger.error(f"File processing failed for {input_file.name}: {e}")

        end_time = time.time()
        logger.info(f"Marker execution took: {end_time - start_time:.2f} seconds")

    except Exception as e:
        logger.error(f"Unexpected error occurred during marker processing: {e}")
        # If marker fails critically, we abort
        raise

    logger.info("Marker Processing completed")

    # --- 3. Ollama LLM Post-processing (Parallel) ---
    if use_postprocess_llm and processed_files:
        logger.info("--- Starting Ollama for Post-processing ---")
        ollama_worker = None
        try:
            # Restart Ollama server
            # We recreate the worker instance to be safe/clean state
            ollama_worker = OllamaWorker()
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

            # Cleanup
            ollama_worker.unload_model()
            ollama_worker.stop_server()

        except Exception as e:
            logger.error(f"Error during Ollama post-processing phase: {e}")
            if ollama_worker:
                ollama_worker.stop_server()

    # Cleanup: Delete original file on success
    # Only delete if we reached here successfully
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
