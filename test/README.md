# Local Testing Environment

This directory contains scripts and configuration files to test the MinerU-vLLM RunPod worker locally.

**Note:** While MinerU can run on a CPU, the vLLM server (used for LLM post-processing) **requires an NVIDIA GPU**. To test the full pipeline locally, you must have the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) installed and a compatible GPU available. If no GPU is available, the vLLM phase will be skipped or fail.

## Prerequisites

*   Docker (with NVIDIA Container Toolkit for GPU support)
*   Python 3 (for generating sample PDFs)
*   `reportlab` Python library (install via `pip install reportlab`)

## Usage

1.  **Generate Sample PDFs**:
    The `create-sample-pdfs.py` script generates two simple PDF files in `test-data/input`.
    ```bash
    python3 create-sample-pdfs.py
    ```

2.  **Run the Test**:
    The `run.sh` script automates the entire testing process:
    *   Creates a build environment.
    *   Checks for sample PDFs (and generates them if missing).
    *   Builds the Docker image.
    *   Runs the container with mounted volumes.
    *   Verifies that Markdown files are generated in the output directory.

    ```bash
    chmod +x run.sh
    ./run.sh
    ```

## Files

*   `create-sample-pdfs.py`: Python script to generate sample PDF files.
*   `run.sh`: Shell script to execute the test.
*   `README.md`: This file.
*   `test-handler.py`: Entry point for testing within the container.
*   `requirements-setup.txt`: Dependencies for the setup script.
*   `*.env`: Environment configuration files for different components.

## License

[GNU General Public License v3.0](../LICENSE)
