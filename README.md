# Dockerized Marker-PDF with Ollama (RunPod Serverless)

This project provides a Dockerized solution for running `marker-pdf` with `Ollama` LLM support as a **RunPod Serverless Worker**. It is designed to process documents (PDF, DOCX, PPTX, etc.) on-demand, leveraging RunPod's GPU infrastructure.

## Architecture

The container runs a Python handler script that listens for jobs from the RunPod API. When a job is received, it:
1.  **Model Setup**:
    *   If `OLLAMA_MODEL` is set, it checks if the model exists locally (pulling it from the Ollama registry if necessary).
    *   If `OLLAMA_MODEL` is *not* set, it attempts to **build** an Ollama model from a cached Hugging Face GGUF file (specified by `OLLAMA_HUGGING_FACE_MODEL_NAME` and `OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION`).
2.  **Processing**: Processes the specified input file or directory using `marker-pdf` (and `marker` for other formats).
3.  **Cleanup**: Deletes the input file upon successful processing.
4.  **Result**: Returns the result (status, processed files, errors).

## Features

*   **Serverless Worker**: Fully compatible with RunPod Serverless.
*   **Multi-Format Support**: Supports `.pdf`, `.pptx`, `.docx`, `.xlsx`, `.html`, and `.epub`.
*   **Ollama Integration**: Leverages a local Ollama instance for enhanced OCR and conversion.
*   **Offline/Cached Models**: Can build Ollama models dynamically from a mounted Hugging Face cache, avoiding repeated network downloads.
*   **NVIDIA Optimized**: Uses the official `pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime` base image for maximum GPU performance.
*   **Configurable**: Job inputs can override default environment variables.

## Prerequisites

*   Docker
*   RunPod Account

## Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/your-username/marker-ollama-worker.git
    cd marker-ollama-worker
    ```

2.  Build the Docker image:
    ```bash
    docker build -t marker-ollama-worker .
    ```

3.  Push the image to a container registry (e.g., Docker Hub, GHCR).

## Model Management

### Ollama model

This worker supports two methods for managing Ollama models:

#### 1. Pull from Cached Ollama Registry (via mounted volume)
Set the `OLLAMA_MODEL` environment variable (e.g., `llama3`). The worker will attempt to pull this model from the cached Ollama registry if it is not present. Note that the cached registry
must be mounted to the directory path specified by the environment variable `OLLAMA_MODELS_DIR`.

#### 2. Build from Hugging Face Cache (Offline/Mounted)
If there is access to the hugging face cache, for example via mounted volumes,
a `GGUF` hugging face model available in that hugging face cache can be specified via the two environment variables
`OLLAMA_HUGGING_FACE_MODEL_NAME` (e.g., `Qwen/Qwen3-VL-8B-Thinking-GGUF`) and `OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION` (e.g., `Q4_K_M`). **For this to work, `OLLAMA_MODEL` must be unset**, such that the ollama model itself is generated from the
hugging face model. The hugging face cache must be available under the mounted volume root, specified by `VOLUME_ROOT_MOUNT_PATH` and the `HF_HOME` environment variable must be set accordingly to the cache path.

The worker will look for the GGUF file in `HF_HOME` and create the Ollama model locally before processing.

### Marker/Surya internal models

To prevent that marker starts downloading its own internal Surya models,
the models must be available before the worker starts.
This can be done by either downloading the models locally via

```sh
python3 -c "from marker.models import create_model_dict; create_model_dict()";
```

and then make the whole marker models inside the Docker container available
at `/app/cache/datalab/models`.

Otherwise, if access to a hugging face cache is available, the following environment variables
can be set

```shell
MODEL_CACHE_DIR=<HF_HOME>/hub
DETECTOR_MODEL_CHECKPOINT=karlo0/surya_line_det_2.20
LAYOUT_MODEL_CHECKPOINT=karlo0/surya_layout_multimodal
FOUNDATION_MODEL_CHECKPOINT=karlo0/surya_text_recognition
RECOGNITION_MODEL_CHECKPOINT=karlo0/surya_text_recognition
TABLE_REC_MODEL_CHECKPOINT=karlo0/surya_tablerec
OCR_ERROR_MODEL_CHECKPOINT=karlo0/tarun-menta_ocr_error_detection
```

where `<HF_HOME>` should be the path to the mounted hugging face cache.
Note: The models `karlo0/...` where obtained by downloading the models
directly from marker as described by the above python command and then
re-uploaded to hugging face. This should ensure that exactly the required
models for marker are used.

### Pre-downloading Models
To populate your volume with models, use the utilities provided in `config/download-models`. See [config/download-models/README.md](config/download-models/README.md) for instructions.

## Usage

### RunPod Deployment

1.  **Create a Template**: In RunPod, create a new Serverless Template.
    *   **Image Name**: Your pushed image (e.g., `ghcr.io/your-username/marker-ollama-worker:latest`).
    *   **Container Disk Size**: 20GB (recommended).
    *   **Environment Variables**: Set defaults (see below).

2.  **Create an Endpoint**: Create a new Serverless Endpoint using the template.

### Job Input Format

You can trigger the worker with a JSON payload. All fields are optional and will fall back to environment variables if not provided.

```json
{
  "input": {
    "storage_bucket_path": "/workspace",
    "input_dir": "input/my_document.pdf", 
    "output_dir": "output",
    "ollama_model": "llama3",
    "marker_workers": 2,
    "marker_paginate_output": false,
    "marker_force_ocr": false,
    "marker_disable_multiprocessing": false,
    "marker_block_correction_prompt": "Optional custom prompt"
  }
}
```

*   `input_dir`: Can be a specific file path or a directory relative to `storage_bucket_path`. Supported formats: PDF, PPTX, DOCX, XLSX, HTML, EPUB.

### Environment Variables

| Variable                                 | Description                                           | Default                                          |
|:-----------------------------------------|:------------------------------------------------------|:-------------------------------------------------|
| `VOLUME_ROOT_MOUNT_PATH`                 | Base path for storage (Required).                     | **None** (Must be set)                           |
| `INPUT_DIR`                              | Default input directory relative to root mount.       | `input`                                          |
| `OUTPUT_DIR`                             | Default output directory relative to root mount.      | `output`                                         |
| `USE_POSTPROCESS_LLM`                    | Enable LLM post-processing.                           | `yes`                                            |
| `OLLAMA_MODEL`                           | Name of the Ollama model to use/pull.                 | (Optional)                                       |
| `OLLAMA_HUGGING_FACE_MODEL_NAME`         | HF Model ID to build from (if `OLLAMA_MODEL` unset).  | (Required if `OLLAMA_MODEL` unset & LLM enabled) |
| `OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION` | Quantization string to match GGUF file.               | (Required if `OLLAMA_MODEL` unset & LLM enabled) |
| `HF_HOME`                                | Path to Hugging Face cache.                           | `${VOLUME_ROOT_MOUNT_PATH}/huggingface-cache`    |
| `OLLAMA_MODELS_DIR`                      | Directory for Ollama models (relative to root mount). | `/.ollama/models`                                |
| `MARKER_WORKERS`                         | Number of worker processes.                           | **None** (Marker determines it automatically)    |
| `MARKER_DEBUG`                           | Enable debug mode.                                    | `False`                                          |

### Additional Configuration Variables

The following variables can also be set to further customize the environment, though they typically have sensible defaults or are managed internally.

**Surya / Marker Models**

| Variable                       | Description                                                     |
|:-------------------------------|:----------------------------------------------------------------|
| `MODEL_CACHE_DIR`              | Cache directory for models. Default: `/v/huggingface-cache/hub` |
| `DETECTOR_MODEL_CHECKPOINT`    | Detection model checkpoint.                                     |
| `LAYOUT_MODEL_CHECKPOINT`      | Layout model checkpoint.                                        |
| `FOUNDATION_MODEL_CHECKPOINT`  | Foundation model checkpoint.                                    |
| `RECOGNITION_MODEL_CHECKPOINT` | Recognition model checkpoint.                                   |
| `TABLE_REC_MODEL_CHECKPOINT`   | Table recognition model checkpoint.                             |
| `OCR_ERROR_MODEL_CHECKPOINT`   | OCR error detection model checkpoint.                           |

**Tools / Performance**

| Tool             | Variable                      | Description                                  | Default                  |
|:-----------------|:------------------------------|:---------------------------------------------|:-------------------------|
| **Python**       | `PYTHONUNBUFFERED`            | Force unbuffered stdout/stderr.              | `1`                      |
| **Hugging Face** | `HF_HUB_OFFLINE`              | Run Hugging Face Hub in offline mode.        | `1`                      |
| **Ollama**       | `OLLAMA_BASE_URL`             | Base URL for Ollama server.                  | `http://127.0.0.1:11434` |
| **PyTorch**      | `PYTORCH_ENABLE_MPS_FALLBACK` | Fallback to CPU if MPS ops aren't supported. | `1`                      |
| **PyTorch**      | `TORCH_NUM_THREADS`           | Threads for intraop parallelism on CPU.      | `1`                      |
| **PyTorch**      | `OMP_NUM_THREADS`             | Threads for OpenMP parallel regions.         | `1`                      |
| **PyTorch**      | `MKL_NUM_THREADS`             | Threads for Intel MKL library.               | `1`                      |
| **PyTorch**      | `TORCH_DEVICE`                | Device to use (`cpu`, `cuda`, `mps`).        | Auto-detected            |

**Marker Specific**

| Variable              | Description                               |
|:----------------------|:------------------------------------------|
| `BASE_DIR`            | Base directory for marker operations.     |
| `OUTPUT_ENCODING`     | Encoding for output text (e.g., `utf-8`). |
| `OUTPUT_IMAGE_FORMAT` | Format for output images (e.g., `JPEG`).  |

## Local Testing

You can test the handler logic locally using the provided test scripts.

1.  **Run the Test**:
    The `test/run.sh` script sets up a local environment and runs the handler with a sample payload.
    ```bash
    cd test
    ./run.sh
    ```

## Releasing

To release a new version of the project, use the `release.sh` script. This script updates the version in `VERSION` and `requirements.txt`, generates a changelog, commits the changes, creates a git tag, and pushes everything to the remote repository.

```bash
./release.sh <new_version>
```

Example:
```bash
./release.sh 1.10.3
```

This will trigger the GitHub Action to build and push the Docker image with the new version tag.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

[GNU General Public License v3.0](LICENSE)
