#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---

# Set default values for environment variables if not provided
STORAGE_BUCKET_PATH=${STORAGE_BUCKET_PATH:-"/workspace"}
INPUT_DIR=${INPUT_DIR:-"input"}
OUTPUT_DIR=${OUTPUT_DIR:-"output"}
OLLAMA_MODEL=${OLLAMA_MODEL:-"llama3"}
OLLAMA_MODELS_DIR=${OLLAMA_MODELS_DIR:-"/root/.ollama/models"}

# Construct absolute paths
INPUT_PATH="${STORAGE_BUCKET_PATH}/${INPUT_DIR}"
OUTPUT_PATH="${STORAGE_BUCKET_PATH}/${OUTPUT_DIR}"

echo "--- Starting Marker-PDF with Ollama ---"
echo "Storage Bucket Path: $STORAGE_BUCKET_PATH"
echo "Input Directory: $INPUT_PATH"
echo "Output Directory: $OUTPUT_PATH"
echo "Ollama Model: $OLLAMA_MODEL"
echo "Ollama Models Directory: $OLLAMA_MODELS_DIR"

# --- 1. Configure Ollama ---

# Set the OLLAMA_MODELS environment variable so Ollama knows where to store/find models.
export OLLAMA_MODELS="$OLLAMA_MODELS_DIR"

# Ensure the models directory exists
mkdir -p "$OLLAMA_MODELS_DIR"

# --- 2. Start Ollama ---

echo "Starting Ollama service..."
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

# --- 4. Pull Model ---

echo "Checking for model: $OLLAMA_MODEL"
# Check if the model is already pulled.
# 'ollama list' outputs a list of models. We grep for the model name.
# We use '|| true' to prevent set -e from exiting if grep finds nothing.
if ollama list | grep -q "$OLLAMA_MODEL"; then
    echo "Model $OLLAMA_MODEL already exists locally."
else
    echo "Model $OLLAMA_MODEL not found locally. Pulling..."
    ollama pull "$OLLAMA_MODEL"
    echo "Model $OLLAMA_MODEL pulled successfully."
fi

# --- 5. Construct Command Arguments ---

# Use a bash array for arguments to handle spaces and quoting correctly
MARKER_ARGS=()

# Add optional arguments based on environment variables
if [ -n "$MARKER_BLOCK_CORRECTION_PROMPT" ]; then
    MARKER_ARGS+=(--block_correction_prompt "$MARKER_BLOCK_CORRECTION_PROMPT")
fi

if [ -n "$MARKER_WORKERS" ]; then
    MARKER_ARGS+=(--workers "$MARKER_WORKERS")
fi

if [ "$MARKER_PAGINATE_OUTPUT" = "true" ]; then
    MARKER_ARGS+=(--paginate_output)
fi

if [ "$MARKER_USE_LLM" = "true" ]; then
    MARKER_ARGS+=(--use_llm)
fi

if [ "$MARKER_FORCE_OCR" = "true" ]; then
    MARKER_ARGS+=(--force_ocr)
fi

# Add the Ollama model argument
MARKER_ARGS+=(--ollama_model "$OLLAMA_MODEL")

echo "Marker command arguments: ${MARKER_ARGS[*]}"

# --- 6. Execute Processing ---

# Check if input directory exists
if [ ! -d "$INPUT_PATH" ]; then
    echo "Error: Input directory $INPUT_PATH does not exist."
    exit 1
fi

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_PATH"

echo "Processing files in $INPUT_PATH..."

# Iterate over PDF files in the input directory
# We use a while loop with find to handle filenames with spaces correctly
find "$INPUT_PATH" -name "*.pdf" -print0 | while IFS= read -r -d '' file; do
    echo "Processing file: $file"

    # Calculate relative path to maintain directory structure
    REL_PATH="${file#$INPUT_PATH/}"
    REL_DIR=$(dirname "$REL_PATH")

    # Create corresponding output directory
    CURRENT_OUTPUT_DIR="$OUTPUT_PATH/$REL_DIR"
    mkdir -p "$CURRENT_OUTPUT_DIR"

    # Run marker-pdf on the single file
    # We execute the command directly without eval
    echo "Running: marker_single \"$file\" \"$CURRENT_OUTPUT_DIR\" ${MARKER_ARGS[*]}"

    # Temporarily disable set -e for the command execution to handle errors manually
    set +e
    marker_single "$file" "$CURRENT_OUTPUT_DIR" "${MARKER_ARGS[@]}"
    EXIT_CODE=$?
    set -e

    if [ $EXIT_CODE -eq 0 ]; then
        echo "Successfully processed: $file"
        # --- 7. Cleanup ---
        echo "Deleting original file: $file"
        rm "$file"
    else
        echo "Error processing file: $file. Exit code: $EXIT_CODE"
        # Do not delete the file if processing failed
    fi
done

echo "All files processed."

# --- 8. Shutdown ---

echo "Stopping Ollama..."
# Check if process is still running before killing
if kill -0 $OLLAMA_PID 2>/dev/null; then
    kill $OLLAMA_PID
fi

echo "Exiting container."
exit 0
