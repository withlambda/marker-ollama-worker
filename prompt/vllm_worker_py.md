# vLLM Worker Implementation (vllm_worker.py)

## Context
This file manages the lifecycle of the vLLM server subprocess and provides an OpenAI-compatible interface for OCR error correction and image description tasks. It handles VRAM-sensitive transitions from the Marker-PDF phase.

## Interface
### Class: `VllmWorker`
- `__init__(settings: VllmSettings)`: Initializes the worker with validated configuration.
- `__enter__` / `__exit__`: Context manager support for server lifecycle.
- `start_server(vram_recovery_delay: Optional[int])`: Launches the vLLM server and waits for health-check readiness.
- `stop_server()`: Gracefully shuts down the server (SIGTERM then SIGKILL).
- `process_text(text: str, ...)`: High-level entry point for text correction.
- `process_file(file_path: Path, ...)`: Corrects text directly in a file.
- `describe_images(image_paths: List[Path], ...)`: High-level entry for vision tasks.

## Logic
### Server Monitoring
- Health-check polling on `/health` endpoint with a configurable timeout.
- Non-blocking server log capture via `process.communicate(timeout=2.0)` if startup fails.

### Resilience and Retries
- Robust exponential backoff retry loop for both text chunks and vision tasks.
- Automatic server restart attempt if a transient error or subprocess crash is detected mid-job.
- Fault tolerance for vision tasks: returns `[Description unavailable]` placeholder on persistent failure to prevent job crash.

### Token-Aware Processing
- Precision token counting via `tiktoken` (falling back to 4-chars-per-token heuristic).
- Markdown-aware chunking that avoids splitting headers, code blocks, or tables.
- Parallel processing of chunks/images using `asyncio.Semaphore` for concurrency control.

## Goal
Regenerate a robust, async-capable vLLM worker that handles the full server lifecycle, provides precise text chunking via `tiktoken`, and implements high-availability retry logic for both vision and text models.
