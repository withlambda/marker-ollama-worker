# Context
This file, `requirements.txt`, lists the Python dependencies required for the marker-vllm-worker. It ensures that all necessary libraries for PDF processing, API communication, and configuration management are installed with compatible versions.

# Interface

## Main Dependencies
- `psutil==5.9.0`: Used for system and process monitoring.
- `requests==2.31.0`: Standard library for synchronous HTTP requests.
- `marker-pdf==1.10.2`: The core library for PDF-to-Markdown conversion.
- `runpod==1.8.1`: The RunPod SDK for serverless worker integration.
- `openai>=1.0.0`: The official OpenAI client, used here to communicate with the OpenAI-compatible vLLM server.
- `httpx>=0.27.0`: Used for asynchronous HTTP requests and health checks.
- `tiktoken>=0.7.0`: Used for precise token counting (approximate character-to-token ratio fallback is used in code).
- `pydantic==2.12.5`: Data validation and settings management (v2).
- `pydantic-settings==2.12.0`: Extension for Pydantic to handle environment-based settings.

# Logic
The `Dockerfile` uses this file to install the application's Python environment. Versions are pinned (or have minimum versions) to ensure reproducibility and stability across container builds.

# Goal
The prompt file provides the exact list of libraries and versions required to recreate the Python environment for the worker.
