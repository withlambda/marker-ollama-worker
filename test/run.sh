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
#
# This script performs the following actions:
# 1. Sets up a build test directory and copies necessary files.
# 2. Generates sample PDF files for testing if they don't exist.
# 3. Builds the Docker image.
# 4. Runs the Docker container with the test handler and mounted volumes.
# 5. Verifies that Markdown output files are generated.
#
# Prerequisites:
# - Docker installed and running.
# - Python 3 installed.
# - Access to Ollama models and Marker models (mounted via volumes).

set -e

# --- Configuration ---

# set variables
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PARENT_OF_SCRIPT_DIR=$(dirname -- "${SCRIPT_DIR}")

BUILD_TEST_DIR="${PARENT_OF_SCRIPT_DIR}/build/test"
export TEST_INPUT_DIR="${BUILD_TEST_DIR}/test-data/input"
export TEST_OUTPUT_DIR="${BUILD_TEST_DIR}/test-data/output"

DOCKER_CONTAINER="marker-with-ollama-test"
OLLAMA_MODEL="smollm:135m"

rm -rf "${BUILD_TEST_DIR}" && mkdir -p "${BUILD_TEST_DIR}"

cp "${SCRIPT_DIR}"/*.txt \
  "${SCRIPT_DIR}"/*.py \
  "${SCRIPT_DIR}"/*.env \
  "${SCRIPT_DIR}/.dockerignore" \
  "${PARENT_OF_SCRIPT_DIR}/Dockerfile" \
  "${PARENT_OF_SCRIPT_DIR}/requirements.txt" \
  "${PARENT_OF_SCRIPT_DIR}/handler.py" \
  "${PARENT_OF_SCRIPT_DIR}/ollama_worker.py" \
  "${PARENT_OF_SCRIPT_DIR}/utils.py" \
  "${PARENT_OF_SCRIPT_DIR}/settings.py" \
  "${PARENT_OF_SCRIPT_DIR}/block_correction_prompts.json" "${BUILD_TEST_DIR}"

cd "${BUILD_TEST_DIR}" || exit 1

pip install -r requirements-setup.txt

rm -rf "${TEST_INPUT_DIR}"
rm -rf "${TEST_OUTPUT_DIR}"

mkdir -p "${TEST_INPUT_DIR}"
mkdir -p "${TEST_OUTPUT_DIR}"

# --- 1. Check for Sample PDFs ---

echo "Checking for sample PDFs in ${TEST_INPUT_DIR}..."

if [ ! -d "${TEST_INPUT_DIR}" ] || [ -z "$(ls -A "${TEST_INPUT_DIR}")" ]; then
    echo "Sample PDFs not found. Generating them..."
    if ! python3 create-sample-pdfs.py; then
        echo "Error: Failed to generate sample PDFs."
        exit 1
    fi
else
    echo "Sample PDFs found."
fi

# --- 2. Build Docker Image ---

echo "Building Docker image..."

docker_build_cmd=()
docker_build_cmd+=("docker build")
docker_build_cmd+=("-f Dockerfile")
docker_build_cmd+=("-t ${DOCKER_CONTAINER}")
docker_build_cmd+=(".")

echo "Docker build command:"
echo "${docker_build_cmd[*]}"

# shellcheck disable=SC2068
if ! ${docker_build_cmd[@]}
then
    echo "Error: Failed to build Docker image."
    exit 1
fi

# --- 3. Run Container & Test Handler ---

echo "Running container and executing test handler..."

docker_run_cmd=()

docker_run_cmd+=("docker run --rm")
docker_run_cmd+=("--name ${DOCKER_CONTAINER}")
docker_run_cmd+=("--shm-size=2gb")
docker_run_cmd+=("--env-file custom.env")
docker_run_cmd+=("--env-file marker.env")
#docker_run_cmd+=("--env-file surya.env")
docker_run_cmd+=("--env-file tools.env")
docker_run_cmd+=("-v ${HOME}/.ollama/:/v/.ollama/")
##docker_run_cmd+=("-v ${PARENT_OF_SCRIPT_DIR}/models/huggingface:/v/huggingface-cache")
docker_run_cmd+=("-v ${PARENT_OF_SCRIPT_DIR}/models/datalab:/app/cache/datalab")
docker_run_cmd+=("-v ${TEST_INPUT_DIR}:/v/input")
docker_run_cmd+=("-v ${TEST_OUTPUT_DIR}:/v/output")
docker_run_cmd+=("-it")
docker_run_cmd+=("${DOCKER_CONTAINER}")

echo "Docker run command:"
echo "${docker_run_cmd[*]}"

# Debug: Inspect the directory structure of the mounted cache BEFORE running the handler
# This helps confirm if the paths expected by Marker match what is mounted.
#"${docker_run_cmd[@]:0:${#docker_run_cmd[@]}-1}" "${DOCKER_CONTAINER}" ls -R /app/cache/datalab | head -n 30

# shellcheck disable=SC2068
${docker_run_cmd[@]}

EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo "Error: Container exited with non-zero status."
    # Don't exit immediately, check output first.
fi

# --- 4. Verify Output ---

echo "Verifying output in ${TEST_OUTPUT_DIR}..."

# Check if output directory exists
if [ ! -d "${TEST_OUTPUT_DIR}" ]; then
    echo "Error: Output directory not found."
    exit 1
fi

# Check for Markdown files
MD_FILES=$(find "${TEST_OUTPUT_DIR}" -name "*.md")

if [ -z "${MD_FILES}" ]; then
    echo "FAILURE: No Markdown files generated."
    exit 1
else
    echo "SUCCESS: Markdown files generated:"
    echo "${MD_FILES}"
fi

echo "Test completed successfully."
exit 0
