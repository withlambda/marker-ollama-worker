# Create Source Code (RunPod Serverless)

## Goal
Create a Dockerized solution that runs `marker-pdf` with `Ollama` LLM support as a **RunPod Serverless Worker**.

## Architecture
The solution must follow the RunPod Serverless architecture:
1.  **Container Start**: The container starts, launches Ollama in the background, and then starts the Python handler script.
2.  **Handler Loop**: The Python script uses the `runpod` SDK to listen for jobs.
3.  **Job Execution**: When a job is received, the handler processes the request based on the input payload.

## Functionality
The handler `handler.py` should:
1.  Receive a job payload containing configuration overrides (e.g., specific input file/dir, model name, marker options).
2.  If no specific file is provided in the payload, process the configured `INPUT_DIR`.
3.  Ensure the requested Ollama model is available (pulling it if necessary, leveraging the persistent volume).
4.  Run `marker-pdf` to convert the PDF(s).
5.  Return the result (status, list of processed files, or error) to RunPod.

## Configuration
The system should be configurable via **Environment Variables** (defaults) and **Job Input** (overrides).

### Parameters
| Parameter | Env Var | Job Input Key | Description |
| :--- | :--- | :--- | :--- |
| Storage Path | `STORAGE_BUCKET_PATH` | `storage_bucket_path` | Base path for storage. |
| Input Path | `INPUT_DIR` | `input_dir` | Subdirectory or specific file to process. |
| Output Path | `OUTPUT_DIR` | `output_dir` | Subdirectory for output. |
| Ollama Model | `OLLAMA_MODEL` | `ollama_model` | LLM model to use. |
| Models Dir | `OLLAMA_MODELS_DIR` | N/A | Persistent storage for models (Env var only). |
| Workers | `MARKER_WORKERS` | `marker_workers` | Number of workers. |
| Paginate | `MARKER_PAGINATE_OUTPUT` | `marker_paginate_output` | Boolean. |
| Use LLM | `MARKER_USE_LLM` | `marker_use_llm` | Boolean. |
| Force OCR | `MARKER_FORCE_OCR` | `marker_force_ocr` | Boolean. |

## Implementation Details

### Base Image
-   Use **`nvcr.io/nvidia/pytorch:25.04-py3`**. This image is expected to contain PyTorch 2.7.0.
-   Ensure it includes necessary CUDA drivers and is as lightweight as possible while maintaining compatibility.

### Software Versions
-   **Pip**: Upgrade pip to the latest version (`pip install --upgrade pip`).
-   **Marker-PDF**: Install version **`1.10.2`**. This version requires PyTorch 2.7.0.
-   **Ollama**: Install via the official curl script (`curl -fsSL https://ollama.com/install.sh | sh`). Pin to a recent stable version if possible, or ensure the installation method retrieves a stable release.

### Startup Script (`entrypoint.sh`)
1.  **Setup**: Configure `OLLAMA_MODELS` directory.
2.  **Start Ollama**: Launch `ollama serve` in the background.
3.  **Wait**: Wait for Ollama to be ready (health check).
4.  **Start Handler**: Execute `python3 -u handler.py`.

### Handler Script (`handler.py`)
-   Import `runpod`.
-   Define a `handler(job)` function.
-   Inside the handler:
    1.  Parse `job['input']` to get configuration, falling back to `os.environ`.
    2.  Check/Pull the required Ollama model.
    3.  Construct the `marker-pdf` command.
    4.  Execute `marker-pdf`.
    5.  Return a JSON object with the results.
-   Call `runpod.serverless.start({"handler": handler})`.

## Output
Generate the following files:
1.  `Dockerfile`: Updated for serverless (install runpod, set CMD/ENTRYPOINT).
2.  `entrypoint.sh`: Updated to start Ollama then the handler.
3.  `handler.py`: The RunPod serverless handler logic.
4.  `docker-compose.yml`: For local testing (simulating the serverless environment).
5.  `README.md`: Updated with RunPod Serverless deployment instructions and expected JSON input format.

## License

[GNU General Public License v3.0](../LICENSE)
