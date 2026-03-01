import runpod
import os
import subprocess
import requests
from pathlib import Path

ALLOWED_INPUT_FILE_EXTENSIONS = {'.pdf', '.pptx', '.docx', '.xlsx', '.html', '.epub'}

def check_and_pull_model(model_name):
    """
    Checks if the specified Ollama model exists locally.
    If not, pulls it from the registry.
    """
    print(f"Checking for model: {model_name}")
    try:
        # Check if model exists
        response = requests.post("http://localhost:11434/api/show", json={"name": model_name})
        if response.status_code != 200:
            raise RuntimeError(f"Ollama Model '{model_name}' not found.")

        print(f"Load Model '{model_name}' ...")
        subprocess.run(["ollama", "pull", model_name], check=True)
        print(f"Model '{model_name}' loaded successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error managing model '{model_name}': {e}")
        raise
    except Exception as e:
        print(f"Unexpected error checking model '{model_name}': {e}")
        raise

class TextProcessor:
    def __init__(self, value):
        # Check if value is either a string or a number (int, float)
        if not isinstance(value, (str, int, float)):
            raise TypeError("Value must be string or number")
        self.value = value

    def to_lower(self):
        return str(self.value).lower()

    def is_parseable_as_int(self):
        try:
            int(self.value)
            return True
        except (ValueError, TypeError):
            raise ValueError(f"Value '{self.value}' is not parsable as an integer.")

def check_is_dir(path: str):
    if not os.path.isdir(path):
        raise NotADirectoryError(f"Path '{path}' is not a directory.")

def check_is_not_file(path: str):
    if os.path.isfile(path):
        raise ValueError(f"Path '{path}' is a file.")

def check_no_subdirs(path: str):
    subdir_count=sum(1 for entry in os.scandir(path) if entry.is_dir())

    if subdir_count > 0:
        raise ValueError(f"Path '{path}' contains subdirectories.")

def is_empty_dir(path: str) -> bool:
    p = Path(path)
    # Returns True only if it's a directory and contains zero items
    return p.is_dir() and not any(p.iterdir())

def check_is_empty_dir(path: str):
    if os.path.exists(path) and not is_empty_dir(path):
        raise ValueError(f"Directory '{path}' is not empty.")

def validate_document_formats(directory_path: str, allowed_file_extensions: set[str]):
    path = Path(directory_path)

    invalid_files = []

    # Iterate only over files (ignore subdirectories)
    for file in path.iterdir():
        if file.is_file():
            # .suffix returns the extension including the dot (e.g., '.docx')
            if file.suffix.lower() not in allowed_file_extensions:
                invalid_files.append(file.name)

    if invalid_files:
        raise ValueError(
            f"Unsupported file formats found: {', '.join(invalid_files)}. "
            f"Allowed formats are: {', '.join(allowed_file_extensions)}"
        )

def handler(job):
    """
    RunPod Serverless Handler.
    """
    job_input = job.get("input", {})

    # --- Configuration ---
    # Get configuration from job input, falling back to environment variables
    storage_bucket_path = os.environ.get('VOLUME_ROOT_MOUNT_PATH')
    if not storage_bucket_path:
         raise ValueError("Environment variable VOLUME_ROOT_MOUNT_PATH is not set")

    ollama_model = os.environ.get('OLLAMA_MODEL')
    if not ollama_model:
        raise ValueError("Environment variable OLLAMA_MODEL is not set")

    input_dir = job_input.get('input_dir')
    output_dir = job_input.get('output_dir')

    if not input_dir or not output_dir:
        raise ValueError("input_dir and output_dir are required in job input")

    marker_workers = job_input.get('marker_workers', "")
    if marker_workers:
        TextProcessor(marker_workers).is_parseable_as_int()

    marker_paginate_output = TextProcessor(job_input.get('marker_paginate_output', "False")).to_lower()
    marker_use_llm = TextProcessor(job_input.get('marker_use_llm', "False")).to_lower()
    marker_force_ocr = TextProcessor(job_input.get('marker_force_ocr', "False")).to_lower()
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
    # Check that only allowed files are in the input directory
    validate_document_formats(input_path, ALLOWED_INPUT_FILE_EXTENSIONS)

    check_is_not_file(output_path)
    check_is_empty_dir(output_path)

    # Create output directory if not existent
    os.makedirs(output_path, exist_ok=True)

    # --- 1. Ensure Model Exists ---
    if not check_and_pull_model(ollama_model):
        return {"error": f"Failed to pull or verify model: {ollama_model}"}

    print(f"--- Processing Job ---")
    print(f"Input Path: {input_path}")
    print(f"Output Path: {output_path}")
    print(f"Ollama Model: {ollama_model}")

    # --- 2. Construct Marker Command ---
    marker_args = [
        input_path,
        "--output_dir", output_path
    ]

    if marker_workers:
        marker_args.extend(["--workers", str(marker_workers)])

    if marker_paginate_output == "true":
        marker_args.append("--paginate_output")

    if marker_force_ocr == "true":
        marker_args.append("--force_ocr")

    if marker_use_llm == "true":
        marker_args.append("--use_llm")
        marker_args.append("--llm_service=marker.services.ollama.OllamaService")
        marker_args.extend(["--ollama_model", ollama_model])
        if marker_block_correction_prompt:
            marker_args.extend(["--block_correction_prompt", marker_block_correction_prompt])

    # --- 3. Execute Processing ---

    print(f"Marker Processing on {input_path} ...")

    cmd = ["marker"] + marker_args
    print(f"Running command: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"During marker processing an error occurred: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error occurred during marker processing: {e}")
        raise
    print(f"Marker Processing completed")

    # Cleanup: Delete original file on success
    for file in Path(input_path).iterdir():
        if file.is_file():
            file.unlink()  # This deletes the file

    return {
        "status": "completed",
        "message": f"All input files of {input_path} processed."
    }

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
