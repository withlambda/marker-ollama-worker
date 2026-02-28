#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---

# Check that required environment variables are available

# Root path of network volume
: "${VOLUME_ROOT_MOUNT_PATH:?The variable VOLUME_ROOT_MOUNT_PATH must be defined}"

# Hugging Face model name, e.g: Qwen/Qwen3-VL-8B-Thinking-GGUF
: "${HUGGING_FACE_MODEL_NAME:?The variable HUGGING_FACE_MODEL_NAME must be defined}"

#  Hugging face model quantization
: "${HUGGING_FACE_MODEL_QUANTIZATION:?The variable HUGGING_FACE_MODEL_QUANTIZATION must be defined}"

# Hugging face cache dir relative to "${VOLUME_ROOT_MOUNT_PATH}", defaults to /huggingface-cache/hub
HUGGING_FACE_CACHE_DIR=${HUGGING_FACE_CACHE_DIR:-"/huggingface-cache/hub"}

# Set default values for environment variables if not provided
# These are defaults; the handler can override them via job input.
export OLLAMA_MODELS_DIR=${OLLAMA_MODELS_DIR:-"/.ollama/models"}

# --- 1. Configure Ollama ---

# Set the OLLAMA_MODELS environment variable so Ollama knows where to store/find models.
# This allows us to point to a mounted volume (e.g., from a storage bucket).
export OLLAMA_MODELS="${VOLUME_ROOT_MOUNT_PATH}${OLLAMA_MODELS_DIR}"

# Ensure the models directory exists.
# If it's a mounted volume, this might already exist, but mkdir -p is safe.
mkdir -p "$OLLAMA_MODELS"

# --- 2. Start Ollama ---

echo "Starting Ollama service..."
# Start Ollama in the background. It will use OLLAMA_MODELS env var.
ollama serve &
OLLAMA_PID=$!

# --- 3. Health Check ---

echo "Waiting for Ollama to start..."
MAX_RETRIES=30
RETRY_COUNT=0
until curl -s localhost:11434 > /dev/null; do
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "Error: Ollama failed to start after $MAX_RETRIES attempts."
        exit 1
    fi
    echo "Waiting for Ollama... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
    ((RETRY_COUNT++))
done
echo "Ollama is up and running!"

# --- 4. build Ollama model from hugging face model ---

# Construct the base path for the Hugging Face model cache
# Replace '/' with '--' in the model name to match HF cache structure
HF_MODEL_BASE_DIR_PATH="${VOLUME_ROOT_MOUNT_PATH}${HUGGING_FACE_CACHE_DIR}/models--${HUGGING_FACE_MODEL_NAME/\//--}"

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

for file in *"${HUGGING_FACE_MODEL_QUANTIZATION}"*.gguf; do
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
    echo "Error: The desired hugging face model file matching quantization '${HUGGING_FACE_MODEL_QUANTIZATION}' was not found in ${HF_MODEL_SNAPSHOT_PATH}"
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

# --- 5. Start Handler ---

echo "Starting RunPod Handler..."
# Execute the Python handler script.
# -u ensures unbuffered output so logs appear immediately.
python3 -u /handler.py

# Note: The handler script calls runpod.serverless.start(), which blocks.
# If the handler exits, the container should exit.
