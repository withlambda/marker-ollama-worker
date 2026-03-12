# `test/custom.env`

## Context
This file defines environment variables specific to the `marker-ollama-worker` application itself, overriding or setting defaults for the test environment.

## Variables
*   `VOLUME_ROOT_MOUNT_PATH`: `/v` (Root mount point for volumes)
*   `HANDLER_FILE_NAME`: `test-handler.py` (Specifies the test handler instead of the default one)
*   `USE_POSTPROCESS_LLM`: `false` (Disables LLM post-processing by default)
*   `MARKER_DEBUG`: `true` (Enables Marker debug mode)
*   `OLLAMA_HUGGING_FACE_MODEL_NAME`: `unsloth/SmolLM2-135M-Instruct-GGUF` (Example model name)
*   `OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION`: `F16` (Quantization level)
