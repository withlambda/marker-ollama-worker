# `ollama_worker.py`

## Context
This module manages the local Ollama server and provides methods for model management and text processing (OCR correction). It handles starting/stopping the Ollama service, pulling or building models from Hugging Face cache, and parallelizing text processing by chunking.

## Interfaces

### Classes

#### `OllamaWorker`
The main class for interacting with Ollama.

##### Methods

*   `__init__(self) -> None`:
```python
def __init__(self) -> None:
```
Initializes the Ollama client and process state.

*   `start_server(self) -> None`:
```python
def start_server(self) -> None:
```
Starts the Ollama server in the background and waits for it to be ready.

*   `stop_server(self) -> None`:
```python
def stop_server(self) -> None:
```
Stops the Ollama server and cleans up resources.

*   `_wait_for_ready(self, max_retries: int = 30) -> None`:
```python
def _wait_for_ready(
    self,
    max_retries: int = 30
) -> None:
```
Internal helper to wait for the Ollama server to become responsive.

*   `ensure_model(self) -> None`:
```python
def ensure_model(self) -> None:
```
Ensures the required model is available (pulls it or builds it from HF).

*   `_check_model_exists(self, model_name: str) -> bool`:
```python
def _check_model_exists(
    self,
    model_name: str
) -> bool:
```
Internal helper to check if a model exists in Ollama.

*   `_build_from_hf(self) -> None`:
```python
def _build_from_hf(self) -> None:
```
Internal helper to build an Ollama model from a GGUF file in the Hugging Face cache.

*   `_process_single_chunk(self, chunk: str, system_prompt: str, chunk_index: int) -> str`:
```python
def _process_single_chunk(
    self,
    chunk: str,
    system_prompt: str,
    chunk_index: int
) -> str:
```
Internal helper to process a single text chunk with Ollama.

*   `process_text(self, text: str, prompt_template: Optional[str] = None, max_chunk_workers: Optional[int] = None) -> str`:
```python
def process_text(
    self,
    text: str,
    prompt_template: Optional[str] = None,
    max_chunk_workers: Optional[int] = None
) -> str:
```
The primary interface for post-processing text. It chunks the text and processes chunks in parallel.

*   `process_file(self, md_file_path: Path, prompt_template: Optional[str] = None, max_chunk_workers: Optional[int] = None) -> bool`:
```python
def process_file(
    self,
    md_file_path: Path,
    prompt_template: Optional[str] = None,
    max_chunk_workers: Optional[int] = None
) -> bool:
```
Processes a single markdown file with the Ollama model. Reads the file, processes its content using `process_text`, and overwrites the original file.

*   `_get_optimal_chunk_workers(num_chunks: int, max_chunk_workers: Optional[int] = None) -> int`:
```python
@staticmethod
def _get_optimal_chunk_workers(num_chunks: int, max_chunk_workers: Optional[int] = None) -> int:
```
Internal helper to determine the optimal number of parallel chunk workers.

*   `_chunk_text(text: str, chunk_size: Optional[int] = None) -> List[str]`:
```python
@staticmethod
def _chunk_text(
    text: str,
    chunk_size: Optional[int] = None
) -> List[str]:
```
Internal helper to split text into chunks based on characters and newlines.

*   `unload_model(self) -> None`:
```python
def unload_model(self) -> None:
```
Unloads the model from VRAM to free resources.

## Logic
1.  **Service Management**: Uses `subprocess.Popen` to manage the `ollama serve` process.
2.  **Model Building**: Parses the Hugging Face hub structure to find GGUF files and creates Ollama models using `client.create`.
3.  **Parallel Processing**: Uses `ThreadPoolExecutor` to process multiple text chunks simultaneously within a single file, significantly improving throughput on multi-core/GPU systems.
4.  **Error Handling**: Provides fallbacks (e.g., returning original text if LLM processing fails) to ensure robustness.

## Dependencies
*   `os`, `subprocess`, `time`, `logging`
*   `pathlib.Path`
*   `concurrent.futures.ThreadPoolExecutor`
*   `ollama` (Ollama Python client)
