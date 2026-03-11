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

# --- Initial validation and configuration ---

# Root path of network volume
: "${VOLUME_ROOT_MOUNT_PATH:?The variable VOLUME_ROOT_MOUNT_PATH must be defined}"

# Whether to use an LLM for post-processing the OCR output
export USE_POSTPROCESS_LLM="${USE_POSTPROCESS_LLM:-"yes"}"

if [ "${USE_POSTPROCESS_LLM}" != "yes" ] && [ "${USE_POSTPROCESS_LLM}" != "no" ]; then
  echo "The value of the USE_POSTPROCESS_LLM environment variable must be either 'yes' or 'no'"
  exit 1
fi

# Set the Hugging face home variable
export HF_HOME="${HF_HOME:-"${VOLUME_ROOT_MOUNT_PATH}/huggingface-cache"}"

# Set default values for environment variables if not provided
# These are defaults; the handler can override them via job input.
export OLLAMA_MODELS_DIR=${OLLAMA_MODELS_DIR:-"/.ollama/models"}

# Set the OLLAMA_MODELS environment variable so Ollama knows where to store/find models.
# This allows us to point to a mounted volume (e.g., from a storage bucket).
export OLLAMA_MODELS="${VOLUME_ROOT_MOUNT_PATH}${OLLAMA_MODELS_DIR}"

# Ensure the models directory exists.
# If it's a mounted volume, this might already exist, but mkdir -p is safe.
mkdir -p "$OLLAMA_MODELS"

# if OLLAMA_MODEL is not specified, then it is assumed
# that the build should be performed from the hugging face model cache.
if [ -z "${OLLAMA_MODEL}" ] && [ "${USE_POSTPROCESS_LLM}" == "yes" ]; then

  # Hugging Face model name, e.g: Qwen/Qwen3-VL-8B-Thinking-GGUF
  : "${OLLAMA_HUGGING_FACE_MODEL_NAME:?The variable OLLAMA_HUGGING_FACE_MODEL_NAME must be defined}"

  #  Hugging face model quantization
  : "${OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION:?The variable OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION must be defined}"

fi

# set handler file name, defaults to handler.py

export HANDLER_FILE_NAME="${HANDLER_FILE_NAME:-handler.py}"

# set permission for non-root user

chown -R appuser:appgroup "${VOLUME_ROOT_MOUNT_PATH}"
