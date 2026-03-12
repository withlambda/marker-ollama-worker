# `config/download-models/download-models-from-hf.sh`

## Context
This script uses `config/download-models/functions.sh` to download models listed in `marker-models.txt` and `ollama-models.txt`.

## Logic
1.  **Dependencies**:
    *   Sources `functions.sh`.
    *   Uses `hf_download` function.
    *   Uses `process_list_file` function.
2.  **Execution**:
    *   Checks if `MODELS_FILES` environment variable is set. Exits with error if not.
    *   Iterates through comma-separated filenames in `MODELS_FILES`.
    *   Calls `process_list_file -c hf_download -f <file>`.
