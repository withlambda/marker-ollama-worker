# Generate test/run.sh

## Instruction
Generate the file `test/run.sh` with the exact content provided below.

## Content
```bash
#!/bin/bash
# Copyright (C) 2026 withLambda
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# Script to run local tests for the Dockerized Marker-PDF solution (RunPod Serverless).


# --- Configuration ---

# set the roor dir to the build/test dir
BUILD_TEST_DIR="../build/test"
rm -rf "${BUILD_TEST_DIR}" && mkdir -p "${BUILD_TEST_DIR}"

cp ./*.txt \
  ./*.py \
  .dockerignore \
  ../Dockerfile \
  ../requirements.txt \
  ../handler.py "${BUILD_TEST_DIR}"
cp -r ../entrypoint "${BUILD_TEST_DIR}"

cd "${BUILD_TEST_DIR}" || exit 1

pip install -r requirements-setup.txt

export TEST_INPUT_DIR="test-data/input"
export TEST_OUTPUT_DIR="test-data/output"

DOCKER_CONTAINER="marker-with-ollama-test"

rm -rf $TEST_INPUT_DIR
rm -rf $TEST_OUTPUT_DIR

mkdir -p $TEST_INPUT_DIR
mkdir -p $TEST_OUTPUT_DIR

# --- 1. Check for Sample PDFs ---

echo "Checking for sample PDFs in $TEST_INPUT_DIR..."

if [ ! -d "$TEST_INPUT_DIR" ] || [ -z "$(ls -A "$TEST_INPUT_DIR")" ]; then
    echo "Sample PDFs not found. Generating them..."
    python3 create-sample-pdfs.py
    if [ $? -ne 0 ]; then
        echo "Error: Failed to generate sample PDFs."
        exit 1
    fi
else
    echo "Sample PDFs found."
fi


# --- 2. Build Docker Image ---

echo "Building Docker image..."

docker build \
  -f Dockerfile \
  --build-arg STAGE="TEST" \
  --build-arg BASE_IMAGE="python:3.11-slim" \
  -t  ${DOCKER_CONTAINER} .

if [ $? -ne 0 ]; then
    echo "Error: Failed to build Docker image."
    exit 1
fi


# --- 3. Run Container & Test Handler ---

echo "Running container and executing test handler..."

OLLAMA_MODEL="smollm:135m"

docker run --rm \
  --name marker-ollama-test \
  --shm-size=2gb \
  -e "VOLUME_ROOT_MOUNT_PATH=/v" \
  -e "HANDLER_FILE_NAME=test-handler.py" \
  -e "OLLAMA_MODEL=${OLLAMA_MODEL}" \
  -e "TORCH_NUM_THREADS=1" \
  -e "TORCH_DEVICE=cpu" \
  -e "PYTORCH_ENABLE_MPS_FALLBACK=1" \
  -e "OMP_NUM_THREADS=1" \
  -e "MKL_NUM_THREADS=1" \
  -e "OCR_ENGINE=none" \
  -e "OLLAMA_BASE_URL=http://127.0.0.1:11434" \
  -v "${HOME}/.ollama/:/v/.ollama/" \
  -v "$(pwd)/${TEST_INPUT_DIR}:/v/input" \
  -v "$(pwd)/${TEST_OUTPUT_DIR}:/v/output" \
  -it \
  ${DOCKER_CONTAINER}

EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo "Error: Container exited with non-zero status."
    # Don't exit immediately, check output first.
fi

# --- 4. Verify Output ---

echo "Verifying output in $TEST_OUTPUT_DIR..."

# Check if output directory exists
if [ ! -d "$TEST_OUTPUT_DIR" ]; then
    echo "Error: Output directory not found."
    exit 1
fi

# Check for Markdown files
MD_FILES=$(find "$TEST_OUTPUT_DIR" -name "*.md")

if [ -z "$MD_FILES" ]; then
    echo "FAILURE: No Markdown files generated."
    exit 1
else
    echo "SUCCESS: Markdown files generated:"
    echo "$MD_FILES"
fi

echo "Test completed successfully."
exit 0
```
