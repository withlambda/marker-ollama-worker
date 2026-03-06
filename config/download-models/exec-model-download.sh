#!/bin/bash

set -e

SCRIPT_DIR=$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)
DOCKER_FILE_NAME="huggingface-hub.dockerfile"
DOCKER_IMAGE_NAME="hf_hub"
# Files with models to download, comma separated
MODELS_FILES="marker-models.txt,ollama-models.txt"
PYTHON_VERSION="3.11.12"
ENV_FILE_PATH="${SCRIPT_DIR}/.env"

ENV_FILE_ARG=""

if [ -f "${ENV_FILE_PATH}" ]; then
  ENV_FILE_ARG="--env-file ${ENV_FILE_PATH}"
fi

# load functions
. "${SCRIPT_DIR}/functions.sh"

PARENT_OF_SCRIPT_DIR=$( get_parent_dir "${SCRIPT_DIR}" )
GRANDPARENT_OF_SCRIPT_DIR=$( get_parent_dir "${PARENT_OF_SCRIPT_DIR}" )

docker build \
  --build-arg PYTHON_VERSION="${PYTHON_VERSION}" \
  -f "${SCRIPT_DIR}/${DOCKER_FILE_NAME}" \
  -t "${DOCKER_IMAGE_NAME}" \
  "${SCRIPT_DIR}"/.

docker run --rm \
  ${ENV_FILE_ARG} \
  -e "MODELS_FILES=${MODELS_FILES}" \
  -v "${GRANDPARENT_OF_SCRIPT_DIR}/models/huggingface":/app/cache/huggingface \
  -it ${DOCKER_IMAGE_NAME}