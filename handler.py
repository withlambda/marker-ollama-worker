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
Main handler for the marker-vllm-worker.
Orchestrates the conversion of documents using the marker-pdf library and
optional post-processing using a vLLM-powered LLM server.
"""

import atexit
import gc
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional, Any, Dict, Tuple, List

import runpod
import torch
import torch.multiprocessing as mp

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser
from marker.output import text_from_rendered

# Set the multiprocessing start method early (required for CUDA)
try:
    mp.set_start_method("spawn", force=True)
except RuntimeError:
    # Already set, which is fine
    pass

from vllm_worker import VllmWorker
from settings import MarkerSettings, VllmSettings, GlobalConfig
from utils import (
    check_is_dir,
    check_is_not_file,
    check_no_subdirs,
    is_empty_dir,
    check_is_empty_dir,
    clear_directory,
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

# Process-local marker models (each worker process has its own copy)
_MARKER_MODELS: Optional[Dict[str, Any]] = None

def marker_worker_init() -> None:
    """
    Initializes marker models for each worker process.
    This function is called once per worker process when the pool is created.
    Models are loaded into VRAM and stored in process-local _MARKER_MODELS variable.
    """
    global _MARKER_MODELS
    logger.info(f"Worker process with pid {os.getpid()} initializing marker models...")
    _MARKER_MODELS = create_model_dict()

    # Register cleanup on exit
    atexit.register(marker_worker_exit)
    logger.info(f"Worker process with pid {os.getpid()} ready")


def marker_worker_exit() -> None:
    """
    Cleanup function for worker processes.
    Releases marker models and clears CUDA cache when a worker process exits.
    """
    global _MARKER_MODELS
    try:
        if '_MARKER_MODELS' in globals() and _MARKER_MODELS:
            # 1. Clear the dictionary explicitly
            _MARKER_MODELS.clear()
            del _MARKER_MODELS

            # 2. Force Python GC
            gc.collect()

            # 3. Synchronize and clear CUDA
            if torch.cuda.is_available():
                torch.cuda.synchronize() # Wait for all kernels to finish
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()

        logger.info(f"Worker {os.getpid()} cleaned up VRAM.")
    except Exception as e:
        logger.warning(f"Error during worker cleanup: {e}")

def calculate_optimal_marker_workers(
    num_files: int,
    app_config: GlobalConfig,
    marker_config: MarkerSettings,
) -> int:
    """
    Calculates the optimal number of marker worker processes based on
    workload and available VRAM.

    This function prevents GPU out-of-memory errors by ensuring that the
    total VRAM reserved for marker processes (marker_workers * vram_gb_per_worker)
    plus the system reserve (vram_gb_reserve) does not exceed the total
    available GPU memory.

    Args:
        num_files: The number of files in the current processing batch.
        app_config: Global configuration containing total VRAM and reserve.
        marker_config: Marker-specific settings (workers override, VRAM per worker).

    Returns:
        The number of worker processes to instantiate, bounded by workload,
        available VRAM, and a reasonable parallel processing limit (default: 4).
    """
    # Get VRAM configuration

    # Parse optimal_marker_workers
    if marker_config.workers is not None:
        optimal_marker_workers = max(1, marker_config.workers)
    else:
        # Linear/Consistent scaling for marker workers
        optimal_marker_workers = min(
            4,
            num_files,
            (app_config.vram_gb_total - app_config.vram_gb_reserve) // marker_config.vram_gb_per_worker
        )

    optimal_marker_workers = max(1, optimal_marker_workers)

    logger.info(f"Calculated optimal marker workers for {num_files} files: "
                f"marker={optimal_marker_workers}")

    return optimal_marker_workers

def list_extracted_images_for_output_file(
    app_config: GlobalConfig,
    output_file_path: Path
) -> List[Path]:
    """
    Lists extracted image files located next to a marker output file.

    Args:
        app_config (GlobalConfig): Global configuration settings.
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
            if path.is_file() and path.suffix.lower() in app_config.IMAGE_FILE_EXTENSIONS
        ],
        key=lambda path: path.name.lower()
    )

def insert_image_descriptions_to_text_file(
    app_config: GlobalConfig,
    output_file_path: Path,
    image_descriptions: List[Tuple[Path, str]]
) -> bool:
    """
    Inserts generated image descriptions into the converted document.

    This method attempts to place descriptions immediately after their
    corresponding image tags (e.g., Markdown images) within the file.
    If the original image reference cannot be found, descriptions are
    appended as a new section at the end of the file.

    Constraints:
        - Only text-based formats (.md, .txt) are supported to ensure the
          Markdown-formatted descriptions do not corrupt structured outputs
          like JSON or HTML.
        - Descriptions are formatted as blockquotes with explicit start/end
          markers for downstream clarity.

    Args:
        app_config: The global application configuration.
        output_file_path: Path to the main text-based output file.
        image_descriptions: List of (image file path, description text) pairs.

    Returns:
        True if the file was modified, False otherwise.
    """
    if not image_descriptions:
        return False

    # Only insert descriptions into text-based output formats (markdown, plain text).
    # Inserting markdown-formatted descriptions into structured formats like JSON or HTML
    # would produce invalid syntax.
    TEXT_EXTENSIONS = {".md", ".txt"}
    if output_file_path.suffix.lower() not in TEXT_EXTENSIONS:
        logger.debug(f"Skipping image description insertion for non-text file: {output_file_path.name}")
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

    original_text = output_file_path.read_text(encoding=app_config.FILE_ENCODING)
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
                f"\n\n> {app_config.image_description_heading}"
                f"\n> {indented_description}"
                f"\n> {app_config.image_description_end}\n"
            )

            modified_text = re.sub(pattern, rf'\g<0>{insertion}', modified_text, count=1)
        else:
            unplaced_descriptions.append((image_path, description))

    # Fallback: append unplaced descriptions at the end
    if unplaced_descriptions:
        section_lines = ["", app_config.image_description_section_heading, ""]
        for image_path, description in unplaced_descriptions:
            section_lines.append(f"### Image: `{image_path.name}`")
            section_lines.append("")
            # Format as blockquote matching inline insertion format
            indented_description = description.replace("\n", "\n> ")
            section_lines.append(f"> {app_config.image_description_heading}")
            section_lines.append(f"> {indented_description}")
            section_lines.append(f"> {app_config.image_description_end}")
            section_lines.append("")

        section_text = "\n".join(section_lines).strip()
        modified_text = f"{modified_text.rstrip()}\n\n{section_text}\n"

    if modified_text != original_text:
        output_file_path.write_text(modified_text, encoding=app_config.FILE_ENCODING)
        return True

    return False

def _save_marker_output(
    app_config: GlobalConfig,
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
        app_config (GlobalConfig): Global configuration settings.
        out_folder (Path): The directory where output files will be saved.
        file_stem (str): The filename without extension.
        full_text (str): The extracted text from the document.
        out_meta (Dict[str, Any]): Metadata from the conversion process.
        images (Dict[str, Any]): Dictionary of image names and image objects.
        output_format (str): The desired output format (e.g., 'markdown', 'json').

    Returns:
        Path: The path to the main output file.
    """

    extension = app_config.FORMAT_EXTENSIONS[output_format]
    output_file = out_folder / f"{file_stem}{extension}"

    # Save output in the specified format
    output_file.write_text(full_text, encoding=app_config.FILE_ENCODING)

    # Save Metadata
    meta_file = out_folder / f"{file_stem}_meta.json"
    meta_file.write_text(json.dumps(out_meta, indent=4), encoding=app_config.FILE_ENCODING)

    # Save Images
    for img_filename, img in images.items():
        img.save(out_folder / img_filename)

    return output_file

def marker_process_single_file(
    app_config: GlobalConfig,
    file_path: Path,
    marker_config: Dict[str, Any],
    output_base_path: Path,
    output_format: str
) -> Tuple[bool, Optional[Path]]:
    """
    Processes a single file using the provided converter and saves the output.
    Uses process-local marker models loaded during worker initialization.

    Args:
        app_config (GlobalConfig): Global configuration settings.
        file_path (Path): Path to the input file (e.g., .pdf, .docx).
        marker_config (Dict[str, Any]): Configuration for the marker converter.
        output_base_path (Path): The root directory where output for this file will be saved.
        output_format (str): The desired output format (e.g., 'markdown', 'json').

    Returns:
        Tuple[bool, Optional[Path]]: A tuple containing (success_boolean, output_file_path).
    """
    global _MARKER_MODELS
    try:
        logger.info(f"Converting {file_path.name} in process with pid {os.getpid()} ...")

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
            app_config,
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

def extract_vllm_settings_from_job_input(
    app_config: GlobalConfig,
    job_input: Dict[str, Any],
) -> VllmSettings:
    """
    Extracts and validates vLLM-specific settings from the RunPod job input.
    Filters keys starting with 'vllm_' and uses them to instantiate VllmSettings.

    Args:
        app_config (GlobalConfig): The global configuration settings.
        job_input (Dict[str, Any]): The raw input dictionary from the RunPod job.

    Returns:
        VllmSettings: A validated configuration object for vLLM.
    """
    # Valid VllmSettings field names (check via model_fields)
    valid_vllm_fields = set(VllmSettings.model_fields.keys())

    vllm_input = {}
    for k, v in job_input.items():
        if k.startswith("vllm_"):
            if k not in valid_vllm_fields:
                logger.warning(
                    f"Unknown vllm setting '{k}' in job input. "
                    f"Valid fields: {sorted(valid_vllm_fields)}"
                )
            vllm_input[k] = v

    return VllmSettings(app_config, **vllm_input)

def extract_marker_settings_from_job_input(job_input: Dict[str, Any]) -> MarkerSettings:
    """
    Extracts and validates Marker-specific settings from the RunPod job input.
    Filters keys starting with 'marker_' and uses them to instantiate MarkerSettings.

    Args:
        job_input (Dict[str, Any]): The raw input dictionary from the RunPod job.

    Returns:
        MarkerSettings: A validated configuration object for Marker.
    """
    # Valid MarkerSettings field names (check via model_fields)
    valid_marker_fields = set(MarkerSettings.model_fields.keys())

    marker_input = {}
    for k, v in job_input.items():
        if k.startswith("marker_"):
            field_name = k[len("marker_"):]
            if field_name not in valid_marker_fields:
                logger.warning(
                    f"Unknown marker setting '{k}' in job input. "
                    f"Valid fields: {sorted(valid_marker_fields)}"
                )
            marker_input[field_name] = v

    # Add shared parameters
    marker_input["output_format"] = job_input.get("output_format", "markdown")
    return MarkerSettings(**marker_input)

def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    RunPod Serverless Handler for document conversion using marker-pdf and vLLM.

    This function executes the following workflow:
    1.  Initialization: Loads global configuration and initializes VRAM logging.
    2.  Settings Extraction: Parses vLLM and Marker-specific settings from the job input.
    3.  vLLM Setup: If LLM post-processing is enabled, initializes the VllmWorker.
    4.  Path Validation: Resolves and validates input and output directories.
    5.  Resource Calculation: Determines the optimal number of worker processes based on
        available VRAM and the number of files to process.
    6.  Batch Processing: Uses a multiprocessing pool to convert files in parallel:
        -   Each worker process loads its own copy of marker models.
        -   Individual file failures are caught and logged, allowing the batch to continue.
    7.  LLM Post-processing (Optional): If enabled, starts the vLLM server as a subprocess
        and processes the converted text through the model for OCR error correction and image descriptions.
    8.  Cleanup: Deletes input files if requested and returns a summary of the operation.

    Args:
        job (Dict[str, Any]): The RunPod job object containing 'input' parameters.

    Returns:
        Dict[str, Any]: A result dictionary containing:
            - status: 'success', 'completed', or 'partially_completed'.
            - message: Summary description of the operation outcome.
            - failures: List of filenames that failed post-processing (if status is 'partially_completed').
    """

    # --- Configuration and Environment Setup ---
    app_config = setup_config()

    log_vram_usage("Start")

    # Load job input
    job_input = job.get("input", {})

    # Extract structured settings
    vllm_settings: Optional[VllmSettings] = None
    if app_config.use_postprocess_llm:
        vllm_settings = extract_vllm_settings_from_job_input(app_config=app_config, job_input=job_input)
    marker_settings = extract_marker_settings_from_job_input(job_input=job_input)

    vllm_worker: Optional[VllmWorker] = None

    # --- 1. vLLM Worker Setup (Pre-processing) ---
    if app_config.use_postprocess_llm and vllm_settings:
        vllm_worker = VllmWorker(settings=vllm_settings)

    # Read base paths from global config
    storage_bucket_path = app_config.volume_root_mount_path
    cleanup_output_dir = app_config.cleanup_output_dir_before_start

    # Get job-specific configuration
    input_dir = job_input.get('input_dir')
    output_dir = job_input.get('output_dir')
    output_format = marker_settings.output_format

    if output_format not in app_config.VALID_OUTPUT_FORMATS:
        raise ValueError(f"output_format must be one of {app_config.VALID_OUTPUT_FORMATS}")

    if not input_dir or not output_dir:
        raise ValueError("input_dir and output_dir are required in job input")

    delete_input_on_success = bool(job_input.get('delete_input_on_success', False))

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
        clear_directory(output_path)

    os.makedirs(output_path, exist_ok=True)

    # --- Configure Marker (Without internal LLM) ---
    marker_config = {
        "output_format": marker_settings.output_format,
        "output_dir": output_path,
        "debug": marker_settings.debug,
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
            if file.suffix.lower() in app_config.ALLOWED_INPUT_FILE_EXTENSIONS:
                files_to_process.append(file)
            else:
                logger.warning(f"Skipping unsupported file: {file.name}")

    if not files_to_process:
        return {"status": "success", "message": "No supported files found to process."}

    # --- Calculate optimal worker counts ---
    optimal_marker_workers = calculate_optimal_marker_workers(
        num_files=len(files_to_process),
        app_config=app_config,
        marker_config=marker_settings,
    )

    maxtasksperchild_rendered = marker_settings.maxtasksperchild if marker_settings.maxtasksperchild is not None \
        else 'unlimited'

    # --- Execute Marker Processing ---
    logger.info(f"Starting conversion for {len(files_to_process)} files "
                f"with marker using {optimal_marker_workers} workers "
                f"and {maxtasksperchild_rendered} max tasks per worker...")
    start_time = time.time()
    processed_files = [] # Paths of successfully processed output files
    successful_inputs = [] # Original paths of successfully processed files

    try:
        # Prepare arguments for each file
        task_args = [
            (app_config, file_to_process, marker_config, output_path, output_format)
            for file_to_process in files_to_process
        ]

        # Use multiprocessing Pool with worker initialization
        with mp.Pool(
            processes=optimal_marker_workers,
            initializer=marker_worker_init,
            maxtasksperchild=marker_settings.maxtasksperchild  # Recycle workers periodically to free VRAM
        ) as pool:
            # Process files and collect results
            results = pool.starmap(marker_process_single_file, task_args, chunksize=1)

            # Separate successful results from failed ones
            for idx, (success, output_file_path) in enumerate(results):
                if success and output_file_path:
                    processed_files.append(output_file_path)
                    successful_inputs.append(files_to_process[idx])

        end_time = time.time()
        logger.info(f"Marker execution took: {end_time - start_time:.2f} seconds")
        gc.collect()
        torch.cuda.empty_cache()
        log_vram_usage("After Marker")

    except Exception as e:
        logger.error(f"Unexpected error occurred during marker processing: {e}")
        # If marker fails critically, we abort
        raise

    logger.info("Marker Processing completed")

    # --- 3. vLLM LLM Post-processing (Parallel) ---
    failed_post_processing = []
    if app_config.use_postprocess_llm and vllm_worker and processed_files:
        # Note: Marker worker processes have terminated, releasing their VRAM
        # vLLM now has full access to VRAM
        log_vram_usage("Before starting vLLM server")

        logger.info("--- Starting vLLM for Post-processing ---")

        try:
            # Use VllmWorker context manager to start the server and wait for readiness
            with vllm_worker:
                logger.info(f"Post-processing {len(processed_files)} files with {vllm_settings.vllm_chunk_workers} chunk workers...")

                # Process files sequentially, with parallel chunk processing within each file
                for processed_file_path in processed_files:
                    success = vllm_worker.process_file(
                        file_path=processed_file_path,
                        prompt_template=vllm_settings.vllm_block_correction_prompt,
                        max_chunk_workers=vllm_settings.vllm_chunk_workers
                    )

                    if not success:
                        failed_post_processing.append(processed_file_path.name)
                        continue

                    extracted_images = list_extracted_images_for_output_file(app_config, processed_file_path)
                    if not extracted_images:
                        continue

                    image_descriptions = vllm_worker.describe_images(
                        image_paths=extracted_images,
                        prompt_template=vllm_settings.vllm_image_description_prompt,
                        max_image_workers=vllm_settings.vllm_chunk_workers
                    )

                    inserted_descriptions = insert_image_descriptions_to_text_file(
                        app_config=app_config,
                        output_file_path=processed_file_path,
                        image_descriptions=image_descriptions
                    )
                    if inserted_descriptions:
                        logger.info(
                            f"Inserted {len(image_descriptions)} image descriptions into {processed_file_path.name}"
                        )

            torch.cuda.empty_cache()
            log_vram_usage("Final")

        except Exception as e:
            logger.error(f"Critical error during vLLM post-processing phase: {e}")
            # If the vLLM phase fails critically, we still return the Marker results
            # but with a partially_completed status and error message.
            return {
                "status": "partially_completed",
                "message": f"Marker succeeded, but vLLM phase failed critically: {e}",
                "failures": failed_post_processing if failed_post_processing else ["vLLM_phase_crash"]
            }

    # Cleanup: Delete the original file on success
    # Only delete it if we reached here successfully and delete_input_on_success is enabled
    if delete_input_on_success:
        for file_to_process in successful_inputs:
            try:
                file_to_process.unlink()
                logger.info(f"Deleted input file: {file_to_process.name}")
            except Exception as e:
                logger.warning(f"Failed to delete input file {file_to_process}: {e}")

    return {
        "status": "completed" if not failed_post_processing else "partially_completed",
        "message": f"All {len(processed_files)} input files of {input_path.absolute()} were processed successfully.",
        "failures": failed_post_processing if failed_post_processing else None
    }

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
