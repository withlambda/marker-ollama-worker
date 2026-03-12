# `test/run.sh`

## Context
This script automates the process of running local tests for the Dockerized Marker-PDF worker. It sets up a test environment, generates sample data, builds the Docker image, and executes the handler inside the container.

## Logic
1.  **Cleanup**:
    *   Removes `build/test` and its subdirectories.
    *   Creates new `build/test`, `test-data/input`, and `test-data/output` directories.
2.  **Setup**:
    *   Copies `Dockerfile`, `handler.py`, `entrypoint/` directory, and other files (`*.txt`, `*.py`, `*.env`) to `build/test`.
    *   Installs dependencies from `requirements-setup.txt`.
3.  **Data Generation**:
    *   Calls `python3 create-sample-pdfs.py` to generate `test1.pdf` and `test2.pdf`.
4.  **Docker Build**:
    *   Builds the Docker image `marker-with-ollama-test` using `Dockerfile`.
5.  **Docker Run**:
    *   Runs the container with mounted volumes:
        *   `~/.ollama/`: Ollama cache.
        *   `models/datalab`: Marker model cache.
        *   `test-data/input`: Input directory.
        *   `test-data/output`: Output directory.
    *   Executes `test-handler.py` as `HANDLER_FILE_NAME` via `custom.env`.
6.  **Verification**:
    *   Checks if output directory exists.
    *   Looks for generated `.md` files in the output directory.
    *   Prints success message if files found, failure if not.
7.  **Exit**:
    *   Exits with code 0 on success, non-zero on failure.
