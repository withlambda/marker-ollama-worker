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
Main handler for the mineru-vllm-worker.
Orchestrates the conversion of documents using the MinerU library and
optional post-processing using a vLLM-powered LLM server.
"""

import atexit
import gc
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional, Any, Dict, Tuple, List


import runpod
import shutil
import torch
import torch.multiprocessing as mp
import paddle

from mineru.cli.common import MakeMode, do_parse

# Set the multiprocessing start method early (required for CUDA)
try:
    mp.set_start_method("spawn", force=True)
except RuntimeError:
    # Already set, which is fine
    pass

from vllm_worker import VllmWorker
from settings import MinerUSettings, VllmSettings, GlobalConfig
from utils import (
    check_is_dir,
    check_is_not_file,
    check_no_subdirs,
    is_empty_dir,
    check_is_empty_dir,
    clear_directory,
    setup_config,
    log_vram_usage,
    LanguageProcessor
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)




def mineru_worker_init() -> None:
    """
    Initializes MinerU worker process.
    MinerU loads models on demand based on the mineru.json configuration.
    This function verifies the config path and registers cleanup.
    """
    logger.info(f"Worker process with pid {os.getpid()} initializing MinerU...")

    # MinerU config path is expected via environment variable MINERU_TOOLS_CONFIG_PATH
    config_path = os.environ.get("MINERU_TOOLS_CONFIG_PATH")
    if config_path:
        if not Path(config_path).exists():
            logger.warning(f"MinerU config not found at {config_path}. Falling back to defaults.")
        else:
            logger.info(f"MinerU using config from {config_path}")
    else:
        logger.warning("MINERU_TOOLS_CONFIG_PATH not set. MinerU will use default configuration.")

    # Register cleanup on exit
    atexit.register(mineru_worker_exit)
    logger.info(f"Worker process with pid {os.getpid()} ready")


def mineru_worker_exit() -> None:
    """
    Cleanup function for worker processes.
    Releases GPU memory for both PaddlePaddle and PyTorch.
    """
    try:
        # 1. Clear PaddlePaddle cache if available
        if paddle and hasattr(paddle, 'device') and hasattr(paddle.device, 'cuda') and paddle.device.cuda.is_available():
            logger.info(f"Process {os.getpid()}: Clearing PaddlePaddle CUDA cache")
            paddle.device.cuda.empty_cache()

        # 2. Force Python GC
        gc.collect()

        # 3. Synchronize and clear PyTorch CUDA cache
        if torch.cuda.is_available():
            logger.info(f"Process {os.getpid()}: Clearing PyTorch CUDA cache")
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()

        logger.info(f"Worker {os.getpid()} cleaned up VRAM.")
    except Exception as e:
        logger.warning(f"Error during worker cleanup for pid {os.getpid()}: {e}", exc_info=True)

def calculate_optimal_mineru_workers(
    num_files: int,
    app_config: GlobalConfig,
    mineru_config: MinerUSettings,
) -> int:
    """
    Calculates the optimal number of MinerU worker processes based on
    workload and available VRAM.

    This function prevents GPU out-of-memory errors by ensuring that the
    total VRAM reserved for MinerU processes (mineru_workers * vram_gb_per_worker)
    plus the system reserve (vram_gb_reserve) does not exceed the total
    available GPU memory.

    Args:
        num_files: The number of files in the current processing batch.
        app_config: Global configuration containing total VRAM and reserve.
        mineru_config: MinerU-specific settings (workers override, VRAM per worker).

    Returns:
        The number of worker processes to instantiate, bounded by workload,
        available VRAM, and a reasonable parallel processing limit (default: 4).
    """
    # Get VRAM configuration

    # Parse optimal_mineru_workers
    if mineru_config.workers is not None:
        optimal_mineru_workers = max(1, mineru_config.workers)
    else:
        # Linear/Consistent scaling for MinerU workers
        optimal_mineru_workers = min(
            4,
            num_files,
            (app_config.vram_gb_total - app_config.vram_gb_reserve) // mineru_config.vram_gb_per_worker
        )

    optimal_mineru_workers = max(1, optimal_mineru_workers)

    logger.info(f"Calculated optimal MinerU workers for {num_files} files: "
                f"mineru={optimal_mineru_workers}")

    return optimal_mineru_workers

def list_extracted_images_for_output_file(
    app_config: GlobalConfig,
    output_file_path: Path
) -> List[Path]:
    """
    Lists extracted image files located next to or in an 'images/' subfolder
    relative to a MinerU output file.

    Args:
        app_config (GlobalConfig): Global configuration settings.
        output_file_path (Path): Path to the MinerU output text file.

    Returns:
        List[Path]: Sorted image paths found in the same output directory or its 'images' subfolder.
    """
    output_dir = output_file_path.parent
    if not output_dir.exists() or not output_dir.is_dir():
        return []

    image_paths = []
    # Check output_dir
    image_paths.extend([
        path for path in output_dir.iterdir()
        if path.is_file() and path.suffix.lower() in app_config.IMAGE_FILE_EXTENSIONS
    ])

    # Check images/ subfolder (MinerU often puts images here)
    images_subfolder = output_dir / "images"
    if images_subfolder.exists() and images_subfolder.is_dir():
        image_paths.extend([
            path for path in images_subfolder.iterdir()
            if path.is_file() and path.suffix.lower() in app_config.IMAGE_FILE_EXTENSIONS
        ])

    return sorted(image_paths, key=lambda path: path.name.lower())

def insert_image_descriptions_to_text_file(
    app_config: GlobalConfig,
    output_file_path: Path,
    image_descriptions: List[Tuple[Path, str]],
    heading_override: Optional[str] = None,
    end_override: Optional[str] = None,
    section_heading_override: Optional[str] = None,
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
        heading_override: Optional override for the description start marker.
        end_override: Optional override for the description end marker.
        section_heading_override: Optional override for the fallback section heading.

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

    # Use overrides if provided, otherwise fallback to global config defaults
    image_description_heading = heading_override or app_config.image_description_heading
    image_description_end = end_override or app_config.image_description_end
    image_description_section_heading = section_heading_override or app_config.image_description_section_heading

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
                f"\n\n> {image_description_heading}"
                f"\n> {indented_description}"
                f"\n> {image_description_end}\n"
            )

            modified_text = re.sub(pattern, rf'\g<0>{insertion}', modified_text, count=1)
        else:
            unplaced_descriptions.append((image_path, description))

    # Fallback: append unplaced descriptions at the end
    if unplaced_descriptions:
        section_lines = ["", image_description_section_heading, ""]
        for image_path, description in unplaced_descriptions:
            section_lines.append(f"### Image: `{image_path.name}`")
            section_lines.append("")
            # Format as blockquote matching inline insertion format
            indented_description = description.replace("\n", "\n> ")
            section_lines.append(f"> {image_description_heading}")
            section_lines.append(f"> {indented_description}")
            section_lines.append(f"> {image_description_end}")
            section_lines.append("")

        section_text = "\n".join(section_lines).strip()
        modified_text = f"{modified_text.rstrip()}\n\n{section_text}\n"

    if modified_text != original_text:
        output_file_path.write_text(modified_text, encoding=app_config.FILE_ENCODING)
        return True

    return False

def _parse_mineru_page_range(page_range: Optional[str]) -> Tuple[int, Optional[int]]:
    """
    Parses a page range string into start_page_id and end_page_id.
    MinerU uses 0-indexed page IDs.
    Supports formats: "0-5", "5" (single page).
    """
    if not page_range:
        return 0, None
    try:
        if "-" in page_range:
            parts = page_range.split("-")
            start = int(parts[0])
            end = int(parts[1])
            return start, end
        else:
            page = int(page_range)
            return page, page
    except (ValueError, IndexError):
        logger.warning(f"Invalid MinerU page range format: '{page_range}'. Processing entire file.")
        return 0, None


def mineru_process_single_file(
    app_config: GlobalConfig,
    file_path: Path,
    mineru_config_dict: Dict[str, Any],
    output_base_path: Path,
    output_format: str
) -> Tuple[bool, Optional[Path]]:
    """
    Processes a single PDF file using MinerU.
    Uses process-local MinerU components.

    Args:
        app_config (GlobalConfig): Global configuration settings.
        file_path (Path): Path to the input file (e.g., .pdf).
        mineru_config_dict (Dict[str, Any]): Configuration for the MinerU converter.
        output_base_path (Path): The root directory where output for this file will be saved.
        output_format (str): The desired output format (must be 'markdown').

    Returns:
        Tuple[bool, Optional[Path]]: A tuple containing (success_boolean, output_file_path).
    """
    try:
        logger.info(f"Converting {file_path.name} in process with pid {os.getpid()} ...")

        # Create a subfolder for this file's output
        file_stem = file_path.stem
        out_folder = Path(output_base_path) / file_stem
        out_folder.mkdir(parents=True, exist_ok=True)

        pdf_bytes = file_path.read_bytes()

        # Extract configurations from config dict
        ocr_mode = mineru_config_dict.get("ocr_mode", "auto")
        page_range = mineru_config_dict.get("page_range")
        disable_images = mineru_config_dict.get("disable_image_extraction", False)

        start_page, end_page = _parse_mineru_page_range(page_range)

        do_parse(
            output_dir=str(out_folder),
            pdf_file_names=[file_stem],
            pdf_bytes_list=[pdf_bytes],
            p_lang_list=[""],
            backend="pipeline",
            parse_method=ocr_mode,
            f_draw_layout_bbox=False,
            f_draw_span_bbox=False,
            f_dump_md=True,
            f_dump_middle_json=False,
            f_dump_model_output=False,
            f_dump_orig_pdf=False,
            f_dump_content_list=False,
            f_make_md_mode=MakeMode.MM_MD,
            start_page_id=start_page,
            end_page_id=end_page,
        )

        # --- Normalize Output ---
        # MinerU often creates a subfolder named after the stem inside our out_folder
        # e.g., /app/output/mystem/mystem/mystem.md
        # We want it at /app/output/mystem/mystem.md

        target_md = out_folder / f"{file_stem}.md"

        # Find any produced .md file in out_folder recursively
        md_files = list(out_folder.glob("**/*.md"))
        if not md_files:
             logger.error(f"MinerU failed to produce any markdown file for {file_path.name} in {out_folder}")
             return False, None

        source_md = md_files[0]

        if source_md != target_md:
            # Move the MD file up to the canonical location
            # Use replace to overwrite if it somehow already exists
            source_md.replace(target_md)

            # Check for images subfolder relative to source md
            source_images = source_md.parent / "images"
            target_images = out_folder / "images"

            if source_images.exists() and source_images.is_dir():
                if disable_images:
                    # If image extraction is disabled, remove the images
                    shutil.rmtree(source_images)
                else:
                    # If target_images already exists, we might need to move contents instead of renaming folder
                    if target_images.exists():
                        for img_file in source_images.iterdir():
                            if img_file.is_file():
                                 img_file.replace(target_images / img_file.name)
                        try:
                            source_images.rmdir()
                        except OSError:
                            pass # Non-empty or other issue
                    else:
                        source_images.rename(target_images)

            # Cleanup empty subfolders created by MinerU
            # Iterate through the parents of source_md until we reach out_folder
            curr = source_md.parent
            while curr != out_folder and curr.is_relative_to(out_folder):
                try:
                    curr.rmdir()
                    curr = curr.parent
                except OSError:
                    break # Not empty

        if not target_md.exists():
            logger.error(f"MinerU produced markdown file but it could not be found at {target_md}")
            return False, None

        logger.info(f"Finished {file_path.name}")
        return True, target_md

    except Exception as e:
        logger.error(f"Error processing {file_path.name} with MinerU: {e}", exc_info=True)
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

def extract_mineru_settings_from_job_input(job_input: Dict[str, Any]) -> MinerUSettings:
    """
    Extracts and validates MinerU-specific settings from the RunPod job input.
    Filters keys starting with 'mineru_' and uses them to instantiate MinerUSettings.

    Args:
        job_input (Dict[str, Any]): The raw input dictionary from the RunPod job.

    Returns:
        MinerUSettings: A validated configuration object for MinerU.
    """
    # Valid MinerUSettings field names (check via model_fields)
    valid_mineru_fields = set(MinerUSettings.model_fields.keys())

    mineru_input = {}
    for k, v in job_input.items():
        if k.startswith("mineru_"):
            field_name = k[len("mineru_"):]
            if field_name not in valid_mineru_fields:
                logger.warning(
                    f"Unknown mineru setting '{k}' in job input. "
                    f"Valid fields: {sorted(valid_mineru_fields)}"
                )
            mineru_input[field_name] = v

    # Add shared parameters
    mineru_input["output_format"] = job_input.get("output_format", "markdown")
    return MinerUSettings(**mineru_input)

def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    RunPod Serverless Handler for document conversion using MinerU and vLLM.

    This function executes the following workflow:
    1.  Initialization: Loads global configuration and initializes VRAM logging.
    2.  Settings Extraction: Parses vLLM and MinerU-specific settings from the job input.
    3.  vLLM Setup: If LLM post-processing is enabled, initializes the VllmWorker.
    4.  Path Validation: Resolves and validates input and output directories.
    5.  Resource Calculation: Determines the optimal number of worker processes based on
        available VRAM and the number of files to process.
    6.  Batch Processing: Uses a multiprocessing pool to convert files in parallel:
        -   Each worker process initializes MinerU components.
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
    mineru_settings = extract_mineru_settings_from_job_input(job_input=job_input)

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
    output_format = mineru_settings.output_format

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

    # --- Configure MinerU ---
    mineru_config = {
        "ocr_mode": mineru_settings.ocr_mode,
        "disable_image_extraction": mineru_settings.disable_image_extraction,
        "page_range": mineru_settings.page_range,
        "debug": mineru_settings.debug,
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
    optimal_mineru_workers = calculate_optimal_mineru_workers(
        num_files=len(files_to_process),
        app_config=app_config,
        mineru_config=mineru_settings,
    )

    maxtasksperchild_rendered = mineru_settings.maxtasksperchild if mineru_settings.maxtasksperchild is not None \
        else 'unlimited'

    # --- Execute MinerU Processing ---
    logger.info(f"Starting conversion for {len(files_to_process)} files "
                f"with MinerU using {optimal_mineru_workers} workers "
                f"and {maxtasksperchild_rendered} max tasks per worker...")
    start_time = time.time()
    processed_files = [] # Paths of successfully processed output files
    successful_inputs = [] # Original paths of successfully processed files

    try:
        # Prepare arguments for each file
        task_args = [
            (app_config, file_to_process, mineru_config, output_path, output_format)
            for file_to_process in files_to_process
        ]

        # Use multiprocessing Pool with worker initialization
        with mp.Pool(
            processes=optimal_mineru_workers,
            initializer=mineru_worker_init,
            maxtasksperchild=mineru_settings.maxtasksperchild  # Recycle workers periodically to free VRAM
        ) as pool:
            # Process files and collect results
            results = pool.starmap(mineru_process_single_file, task_args, chunksize=1)

            # Separate successful results from failed ones
            for idx, (success, output_file_path) in enumerate(results):
                if success and output_file_path:
                    processed_files.append(output_file_path)
                    successful_inputs.append(files_to_process[idx])

        end_time = time.time()
        logger.info(f"MinerU execution took: {end_time - start_time:.2f} seconds")
        gc.collect()
        torch.cuda.empty_cache()
        log_vram_usage("After MinerU")

    except Exception as e:
        logger.error(f"Unexpected error occurred during MinerU processing: {e}")
        # If MinerU fails critically, we abort
        raise

    logger.info("MinerU Processing completed")

    # --- 3. vLLM LLM Post-processing (Parallel) ---
    failed_post_processing = []
    if app_config.use_postprocess_llm and vllm_worker and processed_files:
        # Note: MinerU worker processes have terminated, releasing their VRAM
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

                    # Language Inference for Image Descriptions and Localized Markers
                    with open(processed_file_path, 'r', encoding=app_config.FILE_ENCODING) as f:
                        text_sample = f.read(app_config.LANGUAGE_DETECTION_SAMPLE_SIZE)
                    target_lang_code = LanguageProcessor.infer_output_language(text_sample)
                    target_lang_name = LanguageProcessor.resolve_language_name(target_lang_code)
                    logger.info(f"Inferred target language for {processed_file_path.name}: {target_lang_name} ({target_lang_code})")

                    extracted_images = list_extracted_images_for_output_file(app_config, processed_file_path)
                    if not extracted_images:
                        continue

                    image_descriptions = vllm_worker.describe_images(
                        image_paths=extracted_images,
                        prompt_template=vllm_settings.vllm_image_description_prompt,
                        max_image_workers=vllm_settings.vllm_chunk_workers,
                        target_language=target_lang_name
                    )

                    # Resolve localized labels for the inferred language
                    localized_labels = LanguageProcessor.resolve_image_description_labels(target_lang_code, app_config)

                    inserted_descriptions = insert_image_descriptions_to_text_file(
                        app_config=app_config,
                        output_file_path=processed_file_path,
                        image_descriptions=image_descriptions,
                        heading_override=localized_labels["begin_marker"],
                        end_override=localized_labels["end_marker"],
                        section_heading_override=localized_labels["section_heading"]
                    )
                    if inserted_descriptions:
                        logger.info(
                            f"Inserted {len(image_descriptions)} image descriptions into {processed_file_path.name}"
                        )

            torch.cuda.empty_cache()
            log_vram_usage("Final")

        except Exception as e:
            logger.error(f"Critical error during vLLM post-processing phase: {e}")
            # If the vLLM phase fails critically, we still return the MinerU results
            # but with a partially_completed status and error message.
            return {
                "status": "partially_completed",
                "message": f"MinerU succeeded, but vLLM phase failed critically: {e}",
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

    if failed_post_processing:
        return {
            "status": "partially_completed",
            "message": (
                f"{len(processed_files) - len(failed_post_processing)} of {len(processed_files)} "
                f"input files from {input_path.absolute()} were processed successfully; "
                f"{len(failed_post_processing)} failed during LLM post-processing."
            ),
            "failures": failed_post_processing,
        }

    return {
        "status": "completed",
        "message": f"All {len(processed_files)} input files from {input_path.absolute()} were processed successfully.",
        "failures": None,
    }

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
