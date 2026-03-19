# Context
This script, `test/run.sh`, is the primary integration test for the project. It automates the setup of a clean test environment, generates sample data, builds the Docker image, and executes the container to verify the end-to-end PDF-to-Markdown conversion and LLM post-processing logic.

# Interface

## Environment Variables
- `TEST_INPUT_DIR`: Path where sample PDFs are generated (default: `build/test/test-data/input`).
- `TEST_OUTPUT_DIR`: Path where conversion results are saved (default: `build/test/test-data/output`).

## Configuration
- `DOCKER_CONTAINER`: `marker-with-vllm-test`.
- `BUILD_TEST_DIR`: `build/test`.

# Logic

### 1. Environment Setup
- Deletes and recreates the `build/test` directory.
- Copies all necessary source files (`*.py`, `Dockerfile`, `requirements.txt`, etc.) and test configuration (`*.env`, `requirements-setup.txt`) into the build directory.
- Installs local testing dependencies from `requirements-setup.txt`.

### 2. Data Generation
- Checks `TEST_INPUT_DIR` for sample PDFs.
- If missing, it invokes `python3 create-sample-pdfs.py` to generate dummy documents for testing.

### 3. Image Build
- Executes `docker build` using the copied `Dockerfile` and tags the result as `marker-with-vllm-test`.

### 4. Container Execution
- Runs the Docker container with:
  - `--shm-size=2gb`: Required for PyTorch multiprocessing.
  - Multiple `--env-file` arguments to load test settings (`custom.env`, `marker.env`, `tools.env`).
  - Volume mounts for:
    - Model weights (Marker models).
    - Test input directory (`/v/input`).
    - Test output directory (`/v/output`).
- Executes the default handler logic inside the container.

### 5. Verification
- Scans `TEST_OUTPUT_DIR` for the presence of `.md` files.
- Exits with code 0 on success (Markdown files found), or 1 on failure.

# Goal
The prompt file captures the full integration testing pipeline, including the Docker orchestration and volume mounting strategy required to recreate the local verification environment.
