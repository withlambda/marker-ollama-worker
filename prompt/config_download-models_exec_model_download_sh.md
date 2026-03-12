# `config/download-models/exec-model-download.sh`

## Context
This script builds a Docker image to download Hugging Face models specified in text files and runs a container from it.

## Logic
1.  **Configuration**:
    *   `DOCKER_FILE_NAME`: `huggingface-hub.dockerfile`
    *   `DOCKER_IMAGE_NAME`: `hf_hub`
    *   `MODELS_FILES`: `marker-models.txt,ollama-models.txt`
    *   `PYTHON_VERSION`: `3.11.12`
    *   `ENV_FILE_PATH`: `.private.env` (optional)
2.  **Dependencies**:
    *   Sources `functions.sh`.
    *   Uses `get_parent_dir`.
3.  **Docker Build**:
    *   Builds the `hf_hub` image using `docker build`.
    *   Passes `PYTHON_VERSION`.
4.  **Docker Run**:
    *   Runs the container with mounted volumes:
        *   `models/huggingface` -> `/app/cache/huggingface`
    *   Passes `MODELS_FILES` environment variable.
    *   Passes `.private.env` if it exists.
    *   Interactive mode (`-it`).
    *   Remove container on exit (`--rm`).
