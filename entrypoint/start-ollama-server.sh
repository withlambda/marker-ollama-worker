#!/bin/bash

set -e

echo "Starting Ollama service..."
# Start Ollama in the background. It will use OLLAMA_MODELS env var.
# Redirect logs to prevent the background process from blocking the script output
ollama serve > ollama.log 2>&1 &
OLLAMA_PID=$!
echo "OLLAMA PID: ${OLLAMA_PID}"

# --- 3. Health Check ---

echo "Waiting for Ollama to start..."
MAX_RETRIES=30
RETRY_COUNT=0
until curl -s http://127.0.0.1:11434 > /dev/null; do
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "Error: Ollama failed to start after $MAX_RETRIES attempts."
        cat ollama.log
        exit 1
    fi
    echo "Waiting for Ollama... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Retry count: $RETRY_COUNT"
done
echo "Ollama is up and running!"
