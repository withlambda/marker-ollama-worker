# `entrypoint/build-ollama-model.sh`

## Context
This script builds an Ollama model from a cached Hugging Face model if one is not already provided. It is designed to run within the worker's container during startup.

## Logic
1.  **Check for Model**:
    *   If `OLLAMA_MODEL` is set, assume the model is ready and exit.
2.  **Build Model**:
    *   Constructs `HF_MODEL_BASE_DIR_PATH` based on `HF_HOME` and `OLLAMA_HUGGING_FACE_MODEL_NAME`.
    *   Finds the specific revision/snapshot path (`HF_MODEL_SNAPSHOT_PATH`).
    *   Iterates through `.gguf` files in the snapshot directory matching `OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION`.
    *   Identifies the main model file (`HF_MODEL_FILE_NAME`) and adapter file (`HF_MODEL_ADAPTER_FILE_NAME`) if present.
    *   Sets `OLLAMA_MODEL` to the main model file name (without extension).
    *   Checks if the Ollama model already exists using `ollama list`.
3.  **Model Creation**:
    *   If not present, creates a temporary `Modelfile.${OLLAMA_MODEL}`.
    *   Writes `FROM ${FULL_HF_MODEL_PATH}` to the Modelfile.
    *   If an adapter file exists, adds `ADAPTER ${FULL_HF_MODEL_ADAPTER_PATH}`.
    *   Executes `ollama create "${OLLAMA_MODEL}" -f "$MODELFILE_PATH"`.
    *   Removes the temporary `Modelfile`.

## Environment Variables
*   `OLLAMA_MODEL` (Optional/Output)
*   `HF_HOME` (Required if `OLLAMA_MODEL` unset)
*   `OLLAMA_HUGGING_FACE_MODEL_NAME` (Required if `OLLAMA_MODEL` unset)
*   `OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION` (Required if `OLLAMA_MODEL` unset)
