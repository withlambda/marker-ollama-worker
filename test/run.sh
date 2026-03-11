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
  "${SCRIPT_DIR}/.dockerignore" \
  "${PARENT_OF_SCRIPT_DIR}/Dockerfile" \
  "${PARENT_OF_SCRIPT_DIR}/requirements.txt" \
  "${PARENT_OF_SCRIPT_DIR}/handler.py" "${BUILD_TEST_DIR}"
cp -r "${PARENT_OF_SCRIPT_DIR}/entrypoint" "${BUILD_TEST_DIR}"

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

  #-e "OLLAMA_MODEL=${OLLAMA_MODEL}" \

  
 # -e "DETECTOR_MODEL_CHECKPOINT=karlo0/line_det_2.20" \
 # -e "LAYOUT_MODEL_CHECKPOINT=karlo0/surya_layout_multimodal" \
 # -e "FOUNDATION_MODEL_CHECKPOINT=karlo0/surya_text_recognition" \
 # -e "RECOGNITION_MODEL_CHECKPOINT=karlo0/surya_text_recognition" \
 # -e "TABLE_REC_MODEL_CHECKPOINT=datalab-to/surya_tablerec" \
 # -e "OCR_ERROR_MODEL_CHECKPOINT=tarun-menta/ocr_error_detection" \

docker_run_cmd=()

docker_run_cmd+=("docker run --rm")
docker_run_cmd+=("--name ${DOCKER_CONTAINER}")
docker_run_cmd+=("--shm-size=2gb")
docker_run_cmd+=("-e VOLUME_ROOT_MOUNT_PATH=/v")
docker_run_cmd+=("-e HANDLER_FILE_NAME=test-handler.py")
docker_run_cmd+=("-e USE_POSTPROCESS_LLM=no")
docker_run_cmd+=("-e OLLAMA_HUGGING_FACE_MODEL_NAME=unsloth/SmolLM2-135M-Instruct-GGUF")
docker_run_cmd+=("-e OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION=F16")
docker_run_cmd+=("-e OLLAMA_BASE_URL=http://127.0.0.1:11434")
docker_run_cmd+=("-e HF_HUB_OFFLINE=1")
#docker_run_cmd+=("-e MODEL_CACHE_DIR=/v/huggingface-cache/hub")
#docker_run_cmd+=("-e DETECTOR_MODEL_CHECKPOINT=s3://models--karlo0--surya_line_det_2.20/snapshots/6f7abde77d1611fdf3b64709e85eeb9fdb18478d")
#docker_run_cmd+=("-e LAYOUT_MODEL_CHECKPOINT=s3://models--karlo0--surya_layout_multimodal/snapshots/b1832b53e4a2b58e45f7fd64ca0b02fec2a58ecb")
#docker_run_cmd+=("-e FOUNDATION_MODEL_CHECKPOINT=s3://models--karlo0--surya_text_recognition/snapshots/ed1a5d6414c52858c8fec81351719e7bff1843c6")
#docker_run_cmd+=("-e RECOGNITION_MODEL_CHECKPOINT=s3://models--karlo0--surya_text_recognition/snapshots/ed1a5d6414c52858c8fec81351719e7bff1843c6")
#docker_run_cmd+=("-e TABLE_REC_MODEL_CHECKPOINT=s3://models--karlo0--surya_tablerec/snapshots/c64c5cc5d7908af69309d8d6e5c1845105a87625")
#docker_run_cmd+=("-e OCR_ERROR_MODEL_CHECKPOINT=s3://models--karlo0--tarun-menta_ocr_error_detection/snapshots/93ac756c31fb637f40bc68d3df167d9b13de7277")
#docker_run_cmd+=("-e ORDER_MODEL_CHECKPOINT=vikp/surya_order")
#docker_run_cmd+=("-e TEXIFY_MODEL_NAME=vikp/texify")
#docker_run_cmd+=("-e MARKER_MODEL_NAME=vikp/pdf_postprocessor_t5")
docker_run_cmd+=("-e TORCH_NUM_THREADS=1")
docker_run_cmd+=("-e TORCH_DEVICE=cpu")
docker_run_cmd+=("-e PYTORCH_ENABLE_MPS_FALLBACK=1")
docker_run_cmd+=("-e OMP_NUM_THREADS=1")
docker_run_cmd+=("-e MKL_NUM_THREADS=1")
docker_run_cmd+=("-e OCR_ENGINE=none")
docker_run_cmd+=("-v ${HOME}/.ollama/:/v/.ollama/")
#docker_run_cmd+=("-v ${PARENT_OF_SCRIPT_DIR}/models/huggingface:/v/huggingface-cache")
docker_run_cmd+=("-v ${PARENT_OF_SCRIPT_DIR}/models/datalab:/app/cache/datalab")
docker_run_cmd+=("-v ${TEST_INPUT_DIR}:/v/input")
docker_run_cmd+=("-v ${TEST_OUTPUT_DIR}:/v/output")
docker_run_cmd+=("-it")
docker_run_cmd+=("${DOCKER_CONTAINER}")

echo "Docker run command:"
echo "${docker_run_cmd[*]}"

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
