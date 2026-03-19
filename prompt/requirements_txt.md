# Dependencies (requirements.txt)

## Context
Project dependencies for Marker-PDF, RunPod serverless, and the vLLM inference worker.

## Logic
### Dependency Pinning
All dependencies are pinned to specific versions for environment stability:
- `psutil==5.9.0`: Process and system monitoring.
- `requests==2.31.0`: Synchronous HTTP requests.
- `marker-pdf==1.10.2`: Core document conversion engine (vLLM branch compatible).
- `runpod==1.8.1`: Serverless worker infrastructure.
- `openai==2.29.0`: Async client for communicating with the vLLM API.
- `httpx==0.28.1`: Async HTTP engine for API interactions.
- `tiktoken==0.12.0`: Accurate token counting for context window management.
- `vllm==0.17.1`: Standalone inference server for LLM post-processing.
- `pydantic==2.12.5`: Structured configuration and validation.
- `pydantic-settings==2.12.0`: Environment-variable based settings management.

## Goal
Reproduce a stable dependency list that ensures all components (Marker, vLLM, and RunPod) work together with the following specific pinned versions:
- `psutil==5.9.0`, `requests==2.31.0`, `marker-pdf==1.10.2`, `runpod==1.8.1`, `openai==2.29.0`, `httpx==0.28.1`, `tiktoken==0.12.0`, `vllm==0.17.1`, `pydantic==2.12.5`, `pydantic-settings==2.12.0`.
