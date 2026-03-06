#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PARENT_OF_SCRIPT_DIR=$( dirname -- "$SCRIPT_DIR" )

DOCKER_IMAGE_NAME="hf_hub"
MODELS_FILE="marker-models.txt"

docker build -f "${SCRIPT_DIR}/huggingface-hub.dockerfile" -t "${DOCKER_IMAGE_NAME}" "${SCRIPT_DIR}"/.

docker run --rm \
  --env-file "${SCRIPT_DIR}/.env" \
  -e "MODELS_FILE=${MODELS_FILE}" \
  -v "${PARENT_OF_SCRIPT_DIR}/models/huggingface":/app/cache/huggingface \
  -it ${DOCKER_IMAGE_NAME}