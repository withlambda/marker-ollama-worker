# Context
This script, `config/download-models/download-models-from-hf.sh`, is responsible for orchestrating the download of machine learning models from Hugging Face. It reads a list of model IDs from external files and invokes download functions.

# Interface

## Environment Variables
- `MODELS_FILES` (string, required): A comma-separated list of paths to text files. Each text file should contain one Hugging Face model repository ID per line (e.g., `vikp/surya_det2`).

## Inputs
- Helper functions from `functions.sh`.

# Logic
1.  **Initialization**: Locates its own directory and sources `functions.sh`.
2.  **Parsing**: Takes the `MODELS_FILES` variable and converts the comma-separated string into a list of file paths.
3.  **Iteration**: For each file in the list:
    - Logs the file being processed.
    - Calls `process_list_file` with the command `hf_download` and the path to the model list file.

# Goal
The prompt file provides the orchestration logic for model downloads, specifically how it interfaces with `MODELS_FILES` and delegates the actual download work to `functions.sh`.
