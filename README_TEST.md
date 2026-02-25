# Local Testing Environment

This directory contains scripts and configuration files to test the Dockerized Marker-PDF solution locally.

## Prerequisites

*   Docker
*   Docker Compose
*   Python 3 (for generating sample PDFs)
*   `reportlab` Python library (install via `pip install reportlab`)

## Usage

1.  **Generate Sample PDFs**:
    The `create_sample_pdfs.py` script generates two simple PDF files in `test_data/input`.
    ```bash
    python3 create_sample_pdfs.py
    ```

2.  **Run the Test**:
    The `run_test.sh` script automates the entire testing process:
    *   Checks for sample PDFs (and generates them if missing).
    *   Builds the Docker image using `docker-compose.test.yml`.
    *   Runs the container.
    *   Verifies that Markdown files are generated in `test_data/output`.

    ```bash
    chmod +x run_test.sh
    ./run_test.sh
    ```

## Files

*   `create_sample_pdfs.py`: Python script to generate sample PDF files.
*   `docker-compose.test.yml`: Docker Compose configuration for testing.
*   `run_test.sh`: Shell script to execute the test.
*   `README_TEST.md`: This file.
