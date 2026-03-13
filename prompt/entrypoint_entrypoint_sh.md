# `entrypoint/entrypoint.sh`

## Context
This script serves as the primary entry point for the container. It orchestrates the startup process by sourcing other scripts in a specific order.

## Logic
1.  **Validation**:
    *   Exits immediately if any command fails (`set -e`).
    *   Checks if `USE_POSTPROCESS_LLM` is set to "true" (default is "true").
2.  **Configuration**:
    *   Sources `base-validation-and-config.sh`.
3.  **Run Handler**:
    *   Sources `run-handler.sh`.
    *   Note: Ollama startup and model management are handled within the Python handler.
