# Context
This file, `config/download-models/functions.sh`, contains reusable Bash functions for model management. It provides a common interface for downloading models from Hugging Face and processing text-based list files.

# Interface

## Functions

### `hf_download(model_id)`
A wrapper for Hugging Face download CLI.
- **Input**: `model_id` (string, e.g., `vikp/surya_det2`).
- **Logic**: Tries `hf download` first, then falls back to `huggingface-cli download`. If neither is found, it exits with error code 127.

### `process_list_file(options)`
Iterates through a file and executes a command for each non-empty, non-comment line.
- **Options**:
  - `-c <command>`: The shell function or command to execute.
  - `-f <file_path>`: The path to the list file.
- **Logic**:
  - Reads the file line-by-line using `IFS= read -r`.
  - Trims whitespace using `xargs`.
  - Skips empty lines and lines starting with `#`.
  - Invokes `"$command" "$item"`.

### `get_parent_dir(path)`
A simple wrapper around `dirname`.

# Logic
The script uses `set -e` to ensure any failure in a function terminates the process. It is designed to be sourced by other scripts like `download-models-from-hf.sh`.

# Goal
The prompt file captures the utility functions and their error-handling patterns, enabling the exact regeneration of the model download helper library.
