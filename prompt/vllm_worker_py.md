# Context
This file, `vllm_worker.py`, manages the lifecycle of a vLLM server subprocess and handles OpenAI-compatible API communication for document post-processing (OCR error correction) and vision-based image descriptions. It acts as a bridge between the document processing logic and the LLM infrastructure.

# Interface

## Classes

### VllmWorker
Main class for server management and LLM task execution.
- **Constructor**: `__init__(settings: VllmSettings)`
- **Methods**:
  - `__enter__` / `__exit__`: Starts and stops the server when used as a context manager.
  - `start_server(vram_recovery_delay: Optional[int] = None)`: Launches the `vllm serve` subprocess.
  - `stop_server()`: Gracefully shuts down the subprocess (SIGTERM then SIGKILL).
  - `process_text(text: str, prompt_template: Optional[str], max_chunk_workers: int) -> str`: Corrects OCR errors in text.
  - `process_file(file_path: Path, prompt_template: Optional[str], max_chunk_workers: int) -> bool`: Reads, corrects, and overwrites a file.
  - `describe_images(image_paths: List[Path], prompt_template: Optional[str], max_image_workers: int) -> List[Tuple[Path, str]]`: Generates descriptions for a list of images.

# Logic

### Server Lifecycle Management
1.  **VRAM Recovery**: If a delay is configured (default 10s), the worker sleeps before starting the subprocess to allow GPU memory to clear from previous tasks (e.g., Marker).
2.  **Subprocess Execution**: Spawns `vllm serve` with arguments: `vllm_model_path`, `--port`, `--gpu-memory-utilization`, `--max-model-len`, `--max-num-seqs`, and optional `--served-model-name`.
3.  **Readiness Check**: Polls `GET /health` every 2 seconds. It waits up to `vllm_startup_timeout`. If the subprocess dies or times out, it captures the output for diagnostics and raises a `RuntimeError`.
4.  **Automatic Restart**: If the server crashes during an API call, it attempts exactly one restart with a reduced (2s) VRAM recovery delay.

### Text Processing (OCR Correction)
1.  **Chunking**: Splits Markdown text into logical blocks (separated by blank lines), ensuring it doesn't break headers, fenced code blocks (```), or tables (|). If a block exceeds the character budget (computed as `tokens * 4`), it is split by lines.
2.  **Parallel Execution**: Uses `asyncio` with a `Semaphore` (sized by `max_chunk_workers`) to send multiple chunks to the vLLM API concurrently.
3.  **API Call**: Calls `chat.completions.create` with a system prompt (correction instructions) and the chunk as user content.
4.  **Retry Logic**: Implements exponential backoff with jitter for transient errors (503, 504, connection issues, timeouts).
5.  **Reassembly**: Joins corrected chunks with double newlines. If a chunk fails all retries, the original text is used as a fallback.

### Image Description (Vision)
1.  **Preparation**: Encodes image bytes to base64. Maps file extension to MIME type.
2.  **Prompting**: Combines a default instruction ("Provide a precise and concise description...") with any user-provided `prompt_template`.
3.  **API Call**: Sends a multi-modal request (text + `image_url` with data URI) to the vLLM API.
4.  **Concurrency**: Bounded by `max_image_workers` using a semaphore.
5.  **Fallback**: Returns a placeholder string ("> **Image Description:** [Description unavailable]") if an image fails to be described.

### Subprocess Diagnostics
- Uses `process.communicate(timeout=2.0)` during failure handling to capture stdout/stderr without blocking indefinitely, providing context for startup crashes or timeouts.

# Goal
The prompt file provides sufficient detail to regenerate `vllm_worker.py`, including the subprocess orchestration, health polling, Markdown-aware chunking algorithm, async concurrency patterns, and robust error handling.
