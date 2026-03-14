# `ollama_worker.py`

## Context
This module manages the local Ollama server and provides methods for model management and text processing (OCR correction). It handles starting/stopping the Ollama service using process groups for clean termination, pulling or building models from Hugging Face cache, and parallelizing text processing by chunking.

## Interfaces

### Classes

#### `OllamaWorker`
The main class for interacting with Ollama.

##### Methods

*   `__init__(self) -> None`:
    Initializes the Ollama client and process state. Configures the host from `OLLAMA_BASE_URL`.

*   `start_server(self) -> None`:
    Starts the Ollama server (`ollama serve`) in the background with `start_new_session=True`. Redirects output to `ollama.log`. Logs environment and GPU information (via `_log_env_info`) before starting. Supports `OLLAMA_DEBUG=1` if set in environment. Waits for the server to be ready.

*   `_log_env_info(self) -> None`:
    Internal helper to log CUDA availability, GPU device name, VRAM, and relevant environment variables (`CUDA_VISIBLE_DEVICES`, `OLLAMA_MODELS`, etc.). Runs `nvidia-smi -L` to verify GPU status.

*   `stop_server(self) -> None`:
    Stops the Ollama server and its entire process group using `os.killpg` and `signal.SIGTERM`. Falls back to `SIGKILL` if necessary. Ensures no zombie processes remain.

*   `_wait_for_ready(self, max_retries: int = 30) -> None`:
    Internal helper to wait for the Ollama server to become responsive by polling the host.

*   `ensure_model(self) -> None`:
    Ensures the required model is available.
    1. Checks if `OLLAMA_MODEL` exists.
    2. If not, and `OLLAMA_HUGGING_FACE_MODEL_NAME` is set, calls `_build_from_hf`.
    3. Otherwise, attempts to pull the model using the Ollama client.

*   `_check_model_exists(self, model_name: str) -> bool`:
    Checks if a model exists in Ollama. Handles different response formats from the Ollama API (legacy vs modern).

*   `_build_from_hf(self) -> None`:
    Builds an Ollama model from a GGUF file found in the Hugging Face cache (`HF_HOME`).
    1. Scans the HF hub directory for the specified model and quantization.
    2. Constructs a `Modelfile`.
    3. Calls the Ollama CLI (`ollama create`) to register the model in Ollama.

*   `process_text(self, text: str, prompt_template: Optional[str] = None, max_chunk_workers: Optional[int] = None) -> str`:
    Primary interface for post-processing text.
    1. Splits text into chunks.
    2. Uses `ThreadPoolExecutor` to process chunks in parallel via `_process_single_chunk`.
    3. Reassembles the processed chunks.

*   `_process_single_chunk(self, chunk: str, system_prompt: str, chunk_index: int) -> str`:
    Sends a single chunk to Ollama using `client.generate`. Retries once on failure.

*   `process_file(self, file_path: Path, prompt_template: Optional[str] = None, max_chunk_workers: Optional[int] = None) -> bool`:
    Reads a file, processes its content using `process_text`, and overwrites the file with the result.

*   `unload_model(self) -> None`:
    Unloads the model from VRAM by calling `client.generate` with `keep_alive=0`.

*   `initialize_model(self) -> bool`:
    High-level initialization method that starts the server, ensures the model is ready (pulls or builds), and then stops the server to free VRAM for Marker. Returns `True` on success.

## Logic
*   **Process Group Termination**: Uses `start_new_session` and `os.killpg` to ensure that `ollama serve` and any of its child processes are completely terminated.
*   **Resilient API Handling**: Robustly checks for model existence across different versions of the Ollama Python library and API.
*   **Dynamic Parallelism**: Chunk-level parallelism within a single file allows utilizing GPU resources efficiently during the post-processing phase.
*   **Offline First**: Prioritizes building models from a local Hugging Face cache if configured, supporting air-gapped or bandwidth-constrained environments.

## Dependencies
*   `os`, `subprocess`, `time`, `logging`, `signal`, `pathlib`, `concurrent.futures`
*   `ollama` (Ollama Python client)
