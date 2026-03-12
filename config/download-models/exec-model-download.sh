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

set -e

# This script orchestrates the model download process using Docker.
#
# 1. Builds a Docker image containing the necessary Hugging Face tools.
# 2. Runs a container from that image to download the models specified in text files.
#
# Configuration:
#   - DOCKER_FILE_NAME: The Dockerfile to use (huggingface-hub.dockerfile).
#   - MODELS_FILES: A comma-separated list of files containing model IDs (marker-models.txt, ollama-models.txt).
#   - ENV_FILE_PATH: Optional path to an environment file (e.g., for HF_TOKEN).
#
# Output:
#   - Models are downloaded to '../../models/huggingface' relative to this script's location.

SCRIPT_DIR=$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)
DOCKER_FILE_NAME="huggingface-hub.dockerfile"
DOCKER_IMAGE_NAME="hf_hub"
# Files with models to download, comma separated
MODELS_FILES="marker-models.txt,ollama-models.txt"
PYTHON_VERSION="3.11.12"
ENV_FILE_PATH="${SCRIPT_DIR}/.private.env"

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