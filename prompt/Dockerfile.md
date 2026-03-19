# Dockerfile

## Context
A production-ready Dockerfile for a multi-phase GPU-accelerated RunPod Serverless worker.

## Logic
### Base Image
- `pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime`: Optimized for NVIDIA hardware and modern ML tasks.

### Environment Setup
- Redirects caches (`XDG_CACHE_HOME`, `TORCH_HOME`) to a user-owned writable path.
- Configures default vLLM parameters (ports, GPU utilization, context length).

### System and Python Dependencies
- Installs `poppler-utils` and `tesseract-ocr` for document processing.
- Installs all requirements from `requirements.txt` (including `marker-pdf`, `vllm`, and `tiktoken`).
- Pre-downloads Marker font assets to avoid runtime downloads.

### Security and Runtime
- Runs as a non-root `appuser` (UID 1000) for enhanced security.
- Uses `gosu` for potential permission management (installed but not active in default CMD).
- Entrypoint: executes `handler.py` as the main worker process.

## Goal
Regenerate a secure, optimized, and standalone Dockerfile that contains all necessary system/Python dependencies and pre-configured environment variables for a RunPod/vLLM environment.
