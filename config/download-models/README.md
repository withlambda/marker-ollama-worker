# Download Models Configuration

This directory contains scripts and configuration files to download necessary machine learning models from Hugging Face for the `MinerU` application.

## Purpose

The primary purpose of the code in this directory is to automate the downloading of specific Hugging Face models required by `MinerU` (such as layout analysis and OCR models). It uses a Dockerized approach to ensure a consistent environment for downloading and caching these models, which can then be mounted into the main application container.

## Files

*   **`functions.sh`**: A shell script library containing helper functions.
    *   `get_parent_dir`: Returns the parent directory of a given path.
    *   `hf_download`: Wraps the `hf download` command.
    *   `process_list_file`: Reads a file line by line and executes a specified command for each item.
*   **`huggingface-hub.dockerfile`**: A Dockerfile that defines a lightweight Python image with the `huggingface_hub` library installed. It sets up the environment to run the download script.
*   **`vllm-models.txt`**: A text file listing the Hugging Face model repositories for the vLLM server (e.g., multimodal LLM weights).
*   **`download-models-from-hf.sh`**: The script executed inside the Docker container. It loads `functions.sh` and calls `process_list_file` to download the models listed in `vllm-models.txt` using the `hf_download` function.
*   **`exec-model-download.sh`**: The main entry point script for the user.
    *   Builds the Docker image defined in `huggingface-hub.dockerfile`.
    *   Runs the Docker container, mounting a local directory (`../../models/huggingface`) to the container's cache directory (`/app/cache/huggingface`).
    *   Passes the `MODELS_FILES` environment variable to the container.

## Usage

To speed up the download from huggingface create an access token with read access
and store it as `HF_TOKEN` variable in a `private.env` file in the same directory
as this README.md. Follow the [instructions](https://huggingface.co/docs/hub/en/security-tokens) of huggingface on how to get an access token.

To download the models, execute the `exec-model-download.sh` script from this directory:

```bash
cd config/download-models
./exec-model-download.sh
```

This will:
1.  Build the `hf_hub` Docker image.
2.  Run the container.
3.  Download the models listed in `vllm-models.txt` to the `../../models/huggingface` directory on your host machine.

**Note**: Ensure you have Docker installed and running.

## License

[GNU General Public License v3.0](/LICENSE)

