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

# Checks if a variable holds a strict boolean value ("true" or "false").
#
# Arguments:
#   1. var_name (string): The name of the environment variable to check.
#
# Exits:
#   1: If the variable's value is neither "true" nor "false".
check_strict_bool() {
  local var_name="${1:?"Variable name must be provided"}"
  local var_value="${!var_name}"
  if [ "${var_value}" != "true" ] && [ "${var_value}" != "false" ]; then
    echo "The value of the ${var_name} environment variable must be either 'true' or 'false' but was ${var_value}"
    exit 1
  fi
}

# --- Initial validation and configuration ---

# Root path of network volume
: "${VOLUME_ROOT_MOUNT_PATH:?The variable VOLUME_ROOT_MOUNT_PATH must be defined}"

# Whether to use an LLM for post-processing the OCR output
export USE_POSTPROCESS_LLM="${USE_POSTPROCESS_LLM:-"true"}"

# If set to "true", the entire content of the output dir is deleted before starting the marker processing
export CLEANUP_OUTPUT_DIR_BEFORE_START="${CLEANUP_OUTPUT_DIR_BEFORE_START:-"false"}"

check_strict_bool USE_POSTPROCESS_LLM
check_strict_bool CLEANUP_OUTPUT_DIR_BEFORE_START

# Set the Hugging face home variable
export HF_HOME="${HF_HOME:-"${VOLUME_ROOT_MOUNT_PATH}/huggingface-cache"}"

# Set default values for environment variables if not provided
# These are defaults; the handler can override them via job input.
export OLLAMA_MODELS_DIR="${OLLAMA_MODELS_DIR:-"/.ollama/models"}"

# Set the OLLAMA_MODELS environment variable so Ollama knows where to store/find models.
# This allows us to point to a mounted volume (e.g., from a storage bucket).
export OLLAMA_MODELS="${VOLUME_ROOT_MOUNT_PATH}${OLLAMA_MODELS_DIR}"

# Ensure the models directory exists.
# If it's a mounted volume, this might already exist, but mkdir -p is safe.
mkdir -p "$OLLAMA_MODELS"

# if OLLAMA_MODEL is not specified, then it is assumed
# that the build should be performed from the hugging face model cache.
if [ -z "${OLLAMA_MODEL}" ] && [ "${USE_POSTPROCESS_LLM}" = "true" ]; then

  # Hugging Face model name, e.g: Qwen/Qwen3-VL-8B-Thinking-GGUF
  : "${OLLAMA_HUGGING_FACE_MODEL_NAME:?The variable OLLAMA_HUGGING_FACE_MODEL_NAME must be defined}"

  #  Hugging face model quantization
  : "${OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION:?The variable OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION must be defined}"

fi

# set handler file name, defaults to handler.py

export HANDLER_FILE_NAME="${HANDLER_FILE_NAME:-handler.py}"
