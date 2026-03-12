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

# Checks if the environment variable OLLAMA_MODEL is set.
# If so, it assumes the model is to be pulled by Ollama directly and returns early.
# Otherwise, it proceeds to build the Ollama model from a cached Hugging Face model.
#
# Environment Variables:
#   OLLAMA_MODEL (string): The name of the Ollama model.
#   OLLAMA_HUGGING_FACE_MODEL_NAME (string): The name of the Hugging Face model (e.g., Qwen/Qwen3-VL-8B-Thinking-GGUF).
#   OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION (string): The quantization string to match GGUF file.
#   HF_HOME (string): Path to the Hugging Face cache.

if [ -n "${OLLAMA_MODEL}" ]; then
  return
fi

# --- else build Ollama model from hugging face model ---

# Construct the base path for the Hugging Face model cache
# Replace '/' with '--' in the model name to match HF cache structure
HF_MODEL_BASE_DIR_PATH="${HF_HOME}/hub/models--${OLLAMA_HUGGING_FACE_MODEL_NAME/\//--}"

# Check if the model directory exists
if [ ! -d "$HF_MODEL_BASE_DIR_PATH" ]; then
    echo "Error: Hugging Face model directory not found at $HF_MODEL_BASE_DIR_PATH"
    exit 1
fi

# Get the specific revision (snapshot)
if [ -f "$HF_MODEL_BASE_DIR_PATH/refs/main" ]; then
    REF=$(head -n 1 "$HF_MODEL_BASE_DIR_PATH/refs/main")
    HF_MODEL_SNAPSHOT_PATH="${HF_MODEL_BASE_DIR_PATH}/snapshots/${REF}"
else
    # Fallback if refs/main doesn't exist (e.g., manual download or different structure)
    # This assumes there is only one snapshot or we take the first one found.
    # A more robust solution might be needed depending on how the cache is populated.
    HF_MODEL_SNAPSHOT_PATH=$(find "${HF_MODEL_BASE_DIR_PATH}/snapshots" -maxdepth 1 -mindepth 1 -type d | head -n 1)
    if [ -z "$HF_MODEL_SNAPSHOT_PATH" ]; then
         echo "Error: No snapshot found in ${HF_MODEL_BASE_DIR_PATH}/snapshots"
         exit 1
    fi
fi

echo "Using model snapshot at: ${HF_MODEL_SNAPSHOT_PATH}"

cd "${HF_MODEL_SNAPSHOT_PATH}"

HF_MODEL_FILE_NAME=""
HF_MODEL_ADAPTER_FILE_NAME=""

# Iterate over files matching the quantization pattern
# Using find instead of shell globbing for better control and to avoid issues if no files match
# We look for .gguf files containing the quantization string
# Note: The original script checked for symlinks (-L). We'll keep that logic if that's how the cache is structured,
# but usually in snapshots they are actual files or symlinks to blobs.
# We will iterate over all files matching the pattern.

for file in *"${OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION}"*.gguf; do
    # Check if file exists to handle case where glob returns the pattern itself if no matches
    [ -e "$file" ] || continue

    if [[ "$file" == *mmproj* ]]; then
        HF_MODEL_ADAPTER_FILE_NAME="$file"
    else
        HF_MODEL_FILE_NAME="$file"
    fi
done

cd - > /dev/null

# Check the hugging face model is available in the hugging face cache.
if [ -z "$HF_MODEL_FILE_NAME" ]; then
    echo "Error: The desired hugging face model file matching quantization '${OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION}' was not found in ${HF_MODEL_SNAPSHOT_PATH}"
    exit 1
fi

# Define the Ollama model name (remove extension)
export OLLAMA_MODEL="${HF_MODEL_FILE_NAME%.gguf}"
echo "Ollama Model Name: ${OLLAMA_MODEL}"

# only build the model for ollama if not already present
if ! ollama list | grep -q "${OLLAMA_MODEL}"; then

  echo "Building Ollama model '${OLLAMA_MODEL}'..."

  FULL_HF_MODEL_PATH="${HF_MODEL_SNAPSHOT_PATH}/${HF_MODEL_FILE_NAME}"

  # Prepare the Modelfile content
  # We use a temporary file for the Modelfile to avoid complex escaping issues with heredocs inside variables
  MODELFILE_PATH="Modelfile.${OLLAMA_MODEL}"

  echo "FROM ${FULL_HF_MODEL_PATH}" > "$MODELFILE_PATH"

  if [ -n "$HF_MODEL_ADAPTER_FILE_NAME" ]; then
      FULL_HF_MODEL_ADAPTER_PATH="${HF_MODEL_SNAPSHOT_PATH}/${HF_MODEL_ADAPTER_FILE_NAME}"
      echo "ADAPTER ${FULL_HF_MODEL_ADAPTER_PATH}" >> "$MODELFILE_PATH"
  fi

  # Create the model using the Modelfile
  ollama create "${OLLAMA_MODEL}" -f "$MODELFILE_PATH"

  # Cleanup
  rm "$MODELFILE_PATH"

  echo "Ollama model '${OLLAMA_MODEL}' created successfully."
else
  echo "Ollama model '${OLLAMA_MODEL}' already exists. Skipping creation."
fi
