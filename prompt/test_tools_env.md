# `test/tools.env`

## Context
This file configures environment variables for external tools like Python, Hugging Face, Ollama, and PyTorch, primarily for performance tuning or behavior modification.

## Variables
*   `PYTHONUNBUFFERED`: `1` (Unbuffered stdout/stderr)
*   `HF_HUB_OFFLINE`: `1` (Hugging Face offline mode)
*   `OLLAMA_BASE_URL`: `http://127.0.0.1:11434`
*   `PYTORCH_ENABLE_MPS_FALLBACK`: `1`
*   `TORCH_NUM_THREADS`: `1`
*   `OMP_NUM_THREADS`: `1`
*   `MKL_NUM_THREADS`: `1`
