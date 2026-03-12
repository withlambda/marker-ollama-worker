# `config/download-models/functions.sh`

## Context
This script provides helper functions for downloading models from Hugging Face and managing file processing.

## Logic
1.  **Helper Functions**:
    *   `get_parent_dir(path)`: Returns the directory name of a given path.
    *   `hf_download(model_id)`: Wrapper for `hf download` command. Downloads a model from Hugging Face.
2.  **Processing**:
    *   `process_list_file(command, file_path)`:
        *   Takes a command name (`-c`) and a file path (`-f`).
        *   Iterates through each line in the file.
        *   Skips empty lines and comments (`#`).
        *   Executes the given command for each valid line (model ID).
        *   Handles missing arguments or files with errors.
