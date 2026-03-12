# `entrypoint/start-ollama-server.sh`

## Context
This script starts the Ollama server in the background and performs a health check to ensure it is running before proceeding.

## Logic
1.  **Start Ollama**:
    *   Starts `ollama serve` as `appuser` in the background (`&`).
    *   Redirects logs to `ollama.log` and standard error to standard output.
    *   Captures the PID of the Ollama process (`$!`).
    *   Prints "Starting Ollama service...".
    *   Prints the Ollama PID.
2.  **Health Check**:
    *   Waits for Ollama to become responsive using `curl -s http://127.0.0.1:11434`.
    *   Retries every 2 seconds for a maximum of 30 attempts.
    *   Prints "Waiting for Ollama... (RETRY_COUNT/MAX_RETRIES)".
    *   If failed after 30 attempts, prints error message, cats `ollama.log`, and exits with status 1.
    *   If successful, prints "Ollama is up and running!".

## Environment Variables
*   `OLLAMA_MODELS` (Required)
