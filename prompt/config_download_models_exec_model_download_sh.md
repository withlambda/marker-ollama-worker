# Context
This script, `config/download-models/exec-model-download.sh`, orchestrates the model download process using Docker. It builds a dedicated image with Hugging Face tools and runs a container to download specified models into a shared host volume.

# Interface

## Configuration (Hardcoded or Env-based)
- `DOCKER_FILE_NAME`: `huggingface-hub.dockerfile`.
- `DOCKER_IMAGE_NAME`: `hf_hub`.
- `MODELS_FILES`: Comma-separated list of files (default: `marker-models.txt,vllm-models.txt`).
- `PYTHON_VERSION`: `3.11.12`.
- `ENV_FILE_PATH`: `.private.env` (optional, for `HF_TOKEN`).

## Outputs
- Models are downloaded to `../../models/huggingface` relative to the script's directory.

# Logic
1.  **Path Resolution**: Determines script directory and identifies the grandparent directory (project root).
2.  **Environment Check**: If `.private.env` exists, it prepares the `--env-file` argument for `docker run`.
3.  **Build Phase**: Executes `docker build` using `huggingface-hub.dockerfile` with the specified `PYTHON_VERSION`.
4.  **Execution Phase**: Runs the container with:
    - `--rm`: Auto-remove on exit.
    - `-e MODELS_FILES`: Passes the list of model files.
    - `-v`: Mounts the project's `models/huggingface` directory to `/app/cache/huggingface` in the container.
    - Entry point (from Dockerfile): Calls `download-models-from-hf.sh`.

# Goal
The prompt file captures the Docker-based model download orchestration, including the specific build arguments, volume mounts, and environment variable passing required to recreate the workflow exactly.
