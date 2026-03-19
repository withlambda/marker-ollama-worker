# Context
This `Dockerfile` defines the containerized environment for the marker-vllm-worker. It provides a consistent runtime with PyTorch, CUDA, system dependencies for PDF processing (poppler, tesseract), the `marker-pdf` library, and the `vllm` inference server. It replaces the previous Ollama-based architecture with a standalone vLLM server.

# Interface

## Build Arguments (ARGs)
- `PYTORCH_VERSION` (Default: 2.8.0).
- `CUDA_VERSION` (Default: 12.8).
- `CUDNN_VERSION` (Default: 9).
- `DOWNLOAD_MARKER_MODELS` (Default: "false"): If set to "true", downloads Marker's base models during the build phase.
- `BASE_IMAGE`: Defaults to `pytorch/pytorch:${PYTORCH_VERSION}-cuda${CUDA_VERSION}-cudnn${CUDNN_VERSION}-runtime`.

## Runtime Environment Variables (ENVs)
- `PYTHONUNBUFFERED=1`.
- `XDG_CACHE_HOME=/app/cache`, `TORCH_HOME=/app/cache/torch`: Redirects caches to a central location.
- `VLLM_MODEL_PATH=/app/cache/huggingface/hub`.
- `VLLM_PORT=8000`.
- `VLLM_GPU_UTIL=0.90`.
- `VLLM_MAX_MODEL_LEN=16384`.
- `HANDLER_FILE_NAME="handler.py"`.

# Logic

### 1. Base Image and OS Setup
- Uses the official PyTorch CUDA runtime as the base.
- Sets `DEBIAN_FRONTEND=noninteractive` to suppress prompts during `apt-get`.

### 2. System Dependencies
- `poppler-utils`: Essential for PDF rendering and text extraction.
- `tesseract-ocr`: Provides OCR fallback for scanned documents.
- `curl`, `zstd`: Utilities for model downloading and decompression.
- `gcc`, `python3-dev`: Required for compiling some Python extensions (purged after use).
- `gosu`: Used to transition from root to non-root user while preserving permissions.

### 3. Python Environment
- Upgrades `pip`.
- Installs dependencies from `requirements.txt`.
- Installs `vllm` as a standalone server.
- Downloads required fonts for Marker using `download_font()`.
- Conditionally downloads Marker models if `DOWNLOAD_MARKER_MODELS` is true.

### 4. Application Files
- Copies all Python scripts (`*.py`) and the `block_correction_prompts.json` catalog into `/app`.

### 5. Security and Permissions
- Creates a non-root user `appuser` (UID 1000) and group `appgroup`.
- Grants `appuser` ownership of the `/app` directory and their home directory.
- The container is designed to start as root (to allow `utils.py` to fix volume permissions) and then drop to `appuser` for the main handler logic.

### 6. Execution
- Entry point: `python3 -u "${HANDLER_FILE_NAME}"`.

# Goal
The prompt file captures the precise multi-stage build process, dependency tree (including Marker and vLLM), and the security model (root-to-user transition) required to recreate the container exactly.
