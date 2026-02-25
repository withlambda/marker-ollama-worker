# Dockerized Marker-PDF with Ollama

This project provides a Dockerized solution for running `marker-pdf` with `Ollama` LLM support in a single container. It is designed for deployment on serverless GPU platforms like RunPod.io, but can also be run locally.

## Features

*   **Automated PDF Processing**: Monitors a specific input directory for PDF files.
*   **Ollama Integration**: Leverages a local Ollama instance for enhanced OCR and conversion.
*   **Serverless Optimized**: Uses a PyTorch base image optimized for RunPod.io.
*   **Configurable**: Highly customizable via environment variables.
*   **Persistent Models**: Supports mounting a persistent volume for Ollama models to avoid re-downloading.

## Prerequisites

*   Docker
*   Docker Compose (optional, for local testing)
*   NVIDIA GPU (recommended for performance)

## Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/your-username/dockerized-marker-pdf-with-ollama.git
    cd dockerized-marker-pdf-with-ollama
    ```

2.  Build the Docker image:
    ```bash
    docker build -t marker-pdf-ollama .
    ```

## Usage

### Local Testing

1.  Create the necessary directories:
    ```bash
    mkdir -p test_data/input test_data/output ollama_models
    ```

2.  Place your PDF files in `test_data/input`.

3.  Run the container using Docker Compose:
    ```bash
    docker-compose up
    ```

4.  Check the `test_data/output` directory for the generated Markdown files.

### RunPod Deployment

To deploy on RunPod.io, you can use the following template configuration.

**Environment Variables:**

| Variable | Description | Default |
| :--- | :--- | :--- |
| `STORAGE_BUCKET_PATH` | The mount path of the storage bucket. | `/workspace` |
| `INPUT_DIR` | Subdirectory for input PDFs. | `input` |
| `OUTPUT_DIR` | Subdirectory for output Markdown. | `output` |
| `OLLAMA_MODEL` | The LLM model to use (e.g., `llama3`). | `llama3` |
| `OLLAMA_MODELS_DIR` | Directory for Ollama models. | `/root/.ollama/models` |
| `MARKER_WORKERS` | Number of worker processes. | `2` |
| `MARKER_PAGINATE_OUTPUT` | Whether to paginate output (true/false). | `false` |
| `MARKER_USE_LLM` | Whether to use LLM (true/false). | `true` |
| `MARKER_FORCE_OCR` | Whether to force OCR (true/false). | `false` |

**RunPod Template Configuration (JSON Snippet):**

```json
{
  "name": "Marker-PDF with Ollama",
  "imageName": "ghcr.io/your-username/dockerized-marker-pdf-with-ollama:latest",
  "dockerArgs": "",
  "containerDiskSizeGB": 20,
  "volumeInGB": 0,
  "env": [
    {
      "key": "STORAGE_BUCKET_PATH",
      "value": "/workspace"
    },
    {
      "key": "INPUT_DIR",
      "value": "input"
    },
    {
      "key": "OUTPUT_DIR",
      "value": "output"
    },
    {
      "key": "OLLAMA_MODEL",
      "value": "llama3"
    },
    {
      "key": "OLLAMA_MODELS_DIR",
      "value": "/workspace/ollama_models"
    },
    {
      "key": "MARKER_WORKERS",
      "value": "4"
    },
    {
      "key": "MARKER_PAGINATE_OUTPUT",
      "value": "false"
    },
    {
      "key": "MARKER_USE_LLM",
      "value": "true"
    },
    {
      "key": "MARKER_FORCE_OCR",
      "value": "false"
    }
  ],
  "ports": "8888/http",
  "volumeMountPath": "/workspace"
}
```

**Note:** Ensure you have a volume mounted at `/workspace` (or your configured `STORAGE_BUCKET_PATH`) to persist data and models.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

[MIT License](LICENSE)
