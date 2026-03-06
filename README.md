# Dockerized Marker-PDF with Ollama (RunPod Serverless)

This project provides a Dockerized solution for running `marker-pdf` with `Ollama` LLM support as a **RunPod Serverless Worker**. It is designed to process PDF files on-demand, leveraging RunPod's GPU infrastructure.

## Architecture

The container runs a Python handler script that listens for jobs from the RunPod API. When a job is received, it:
1.  Checks if the requested Ollama model is available (pulling it if necessary).
2.  Processes the specified input file or directory using `marker-pdf`.
3.  Returns the result (status, processed files, errors).

## Features

*   **Serverless Worker**: Fully compatible with RunPod Serverless.
*   **Ollama Integration**: Leverages a local Ollama instance for enhanced OCR and conversion.
*   **NVIDIA Optimized**: Uses the official `nvcr.io/nvidia/pytorch:25.04-py3` base image (PyTorch 2.7.0) for maximum GPU performance.
*   **Persistent Models**: Supports mounting a persistent volume (e.g., network volume) for Ollama models to avoid re-downloading.
*   **Configurable**: Job inputs can override default environment variables.

## Prerequisites

*   Docker
*   RunPod Account

## Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/your-username/dockerized-marker-pdf-with-ollama.git
    cd dockerized-marker-pdf-with-ollama
    ```

2.  Build the Docker image:
    ```bash
    docker build -t marker-pdf-serverless .
    ```

3.  Push the image to a container registry (e.g., Docker Hub, GHCR).

## Usage

### RunPod Deployment

1.  **Create a Template**: In RunPod, create a new Serverless Template.
    *   **Image Name**: Your pushed image (e.g., `ghcr.io/your-username/marker-pdf-serverless:latest`).
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
    "marker_workers": 4,
    "marker_paginate_output": false,
    "marker_use_llm": true,
    "marker_force_ocr": false
  }
}
```

*   `input_dir`: Can be a specific file path or a directory relative to `storage_bucket_path`.

### Environment Variables

| Variable | Description | Default |
| :--- | :--- | :--- |
| `VOLUME_ROOT_MOUNT_PATH` | Base path for storage. | `/workspace` |
| `INPUT_DIR` | Default input directory. | `input` |
| `OUTPUT_DIR` | Default output directory. | `output` |
| `OLLAMA_MODEL` | Default LLM model. | `llama3` |
| `OLLAMA_MODELS_DIR` | Directory for Ollama models. | `/root/.ollama/models` |
| `MARKER_WORKERS` | Number of worker processes. | `2` |

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
