# `Dockerfile`

## Context
This Dockerfile defines the environment for the `marker-ollama-worker`. It combines PyTorch, Ollama, and Marker dependencies to create a runtime for converting documents to markdown with optional LLM post-processing. It is based on a specific `pytorch/pytorch` image.

## Arguments

*   `PYTORCH_VERSION`: Default `2.8.0`. The PyTorch version.
*   `CUDA_VERSION`: Default `12.8`. The CUDA version.
*   `CUDNN_VERSION`: Default `9`. The cuDNN version.
*   `OLLAMA_SERVER_VERSION`: Default `0.18.0`. The Ollama version.
*   `DOWNLOAD_MARKER_MODELS`: Default `"false"`. Boolean flag to download marker models during build.
*   `BASE_IMAGE`: Default `pytorch/pytorch:${PYTORCH_VERSION}-cuda${CUDA_VERSION}-cudnn${CUDNN_VERSION}-runtime`.

## Stages

1.  **Load Ollama Image**: Pulls the `ollama/ollama:${OLLAMA_SERVER_VERSION}` image as `ollama-source` to copy the binary.
2.  **Base Image**: Uses `${BASE_IMAGE}` as the foundation.

## Environment Variables

*   `DEBIAN_FRONTEND`: `noninteractive`
*   `PYTHONUNBUFFERED`: `1`
*   `OLLAMA_HOST`: `0.0.0.0`
*   `XDG_CACHE_HOME`: `/app/cache` (Redirected for non-root access)
*   `TORCH_HOME`: `/app/cache/torch`

## Installation Steps

1.  **Install Ollama**: Copies `/usr/bin/ollama` and `/usr/lib/ollama` from the `ollama-source` stage to ensure GPU runners are available.
2.  **Setup Workdir**: Sets `/app` as the working directory.
3.  **Copy Requirements**: Copies `requirements.txt`.
4.  **System Dependencies**:
    *   Creates `${XDG_CACHE_HOME}`.
    *   Updates `apt-get` and installs:
        *   `poppler-utils` (PDF processing)
        *   `tesseract-ocr` (OCR capabilities)
        *   `curl`, `zstd`, `gcc`, `python3-dev`, `gosu`.
    *   Upgrades `pip`.
    *   Installs Python packages from `requirements.txt`.
    *   Downloads Marker fonts (`marker.util.download_font`).
    *   Conditionally downloads Marker models if `DOWNLOAD_MARKER_MODELS` is true.
    *   Purges build dependencies (`gcc`, `python3-dev`) and cleans up `apt` lists.
5.  **Copy Application Code**: Copies `*.py` and `block_correction_prompts.json` to `/app`.
6.  **Create Non-Root User**:
    *   Creates `appuser` (UID 1000) and `appgroup`.
    *   Sets ownership of `/app` and `/home/appuser` to `appuser:appgroup`.
7.  **Start Command**: Sets `CMD [ "python3", "-u", "handler.py" ]`.

## Logic
*   The Dockerfile ensures a consistent environment for running Marker and Ollama.
*   It handles model caching and user permissions to allow running as a non-root user (important for security and some cloud environments).
*   It separates build dependencies from runtime dependencies to keep the image size optimized.
