# `config/download-models/huggingface-hub.dockerfile`

## Context
This Dockerfile creates a minimal Python environment with `huggingface_hub` installed, used specifically for downloading models from Hugging Face.

## Arguments
*   `PYTHON_VERSION`

## Environment Variables
*   `HF_HOME`: `/app/cache/huggingface`

## Installation
1.  **Dependencies**:
    *   `pip install --no-cache-dir huggingface_hub`
2.  **Configuration**:
    *   Creates `/app/cache/huggingface`.
    *   Sets working directory to `/app`.
    *   Copies download scripts (`*.sh`) and model lists (`*.txt`).
3.  **Command**:
    *   `./download-models-from-hf.sh`
