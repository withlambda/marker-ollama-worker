# `entrypoint/base-validation-and-config.sh`

## Context
This script performs initial validation of environment variables and sets up configuration defaults for the Marker worker.

## Logic
1.  **Validation**:
    *   Checks if `VOLUME_ROOT_MOUNT_PATH` is set. Exits with error if not.
    *   Checks if `USE_POSTPROCESS_LLM` is set to "true" or "false". Defaults to "true".
    *   Checks if `CLEANUP_OUTPUT_DIR_BEFORE_START` is set to "true" or "false". Defaults to "false".
2.  **Configuration**:
    *   Sets `HF_HOME` to `${VOLUME_ROOT_MOUNT_PATH}/huggingface-cache` if not already set.
    *   Sets `OLLAMA_MODELS_DIR` to `/.ollama/models` if not already set.
    *   Sets `OLLAMA_MODELS` to `${VOLUME_ROOT_MOUNT_PATH}${OLLAMA_MODELS_DIR}`.
    *   Creates the `${OLLAMA_MODELS}` directory.
3.  **Conditional Checks**:
    *   If `OLLAMA_MODEL` is not set and `USE_POSTPROCESS_LLM` is "true":
        *   Checks if `OLLAMA_HUGGING_FACE_MODEL_NAME` is set. Exits with error if not.
        *   Checks if `OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION` is set. Exits with error if not.
4.  **Handler**:
    *   Sets `HANDLER_FILE_NAME` to `handler.py` if not already set.

## Functions

#### `check_strict_bool`
*   **Args**: `var_name` (string)
*   **Logic**: Checks if the variable value is strictly "true" or "false". Exits with status 1 if invalid.

## Environment Variables
*   `VOLUME_ROOT_MOUNT_PATH` (Required)
*   `USE_POSTPROCESS_LLM` (Optional, Default: "true")
*   `CLEANUP_OUTPUT_DIR_BEFORE_START` (Optional, Default: "false")
*   `HF_HOME` (Optional, Default: `${VOLUME_ROOT_MOUNT_PATH}/huggingface-cache`)
*   `OLLAMA_MODELS_DIR` (Optional, Default: `/.ollama/models`)
*   `OLLAMA_MODELS` (Optional, Default: `${VOLUME_ROOT_MOUNT_PATH}${OLLAMA_MODELS_DIR}`)
*   `OLLAMA_MODEL` (Optional)
*   `OLLAMA_HUGGING_FACE_MODEL_NAME` (Required if `OLLAMA_MODEL` is unset and LLM is enabled)
*   `OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION` (Required if `OLLAMA_MODEL` is unset and LLM is enabled)
*   `HANDLER_FILE_NAME` (Optional, Default: `handler.py`)
