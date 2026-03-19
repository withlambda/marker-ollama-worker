# Context
This file, `utils.py`, provides a set of common utility functions for environment setup, resource monitoring (VRAM), and filesystem validation. It is used by the main handler to ensure the runtime environment is correctly configured and that data paths are valid before processing begins.

# Interface

## Functions

### Environment and Setup
- `setup_config() -> GlobalConfig`: Initializes `GlobalConfig` (triggering Pydantic validation), creates the Hugging Face cache directory, and ensures correct ownership/permissions for mounted volumes if running as root.
- `_update_ownership(*paths: str)`: Recursively changes ownership of paths to `appuser:appgroup` using `chown`. Falls back to `chmod 775` if `chown` fails or `appuser` is missing. Uses `gosu appuser test -w` to verify success.

### VRAM Monitoring
- `get_vram_info() -> Dict[str, Any]`: Executes `nvidia-smi` to query `memory.total, memory.used, memory.free`. Returns a dictionary with these values in MB, or an empty dict if the command fails.
- `log_vram_usage(label: str = "")`: Formats and logs the current VRAM status.

### Path Validation
- `check_is_dir(path)`: Raises `NotADirectoryError` if path is not a directory.
- `check_is_not_file(path)`: Raises `ValueError` if path is an existing file.
- `check_no_subdirs(path)`: Ensures a directory contains only files (ignoring hidden files), raising `ValueError` if subdirectories exist.
- `is_empty_dir(path) -> bool`: Checks for the presence of non-hidden files.
- `check_is_empty_dir(path)`: Raises `ValueError` if the directory exists and contains any non-hidden files.

### Text/Type Utilities
- `TextProcessor.to_bool(value) -> bool`: A robust parser for truthy (`true`, `1`, `yes`, `on`) and falsy (`false`, `0`, `no`, `off`) values across multiple input types (str, int, float, bool).

# Logic

### setup_config Workflow
1.  Instantiates `GlobalConfig`.
2.  If `use_postprocess_llm` is True:
    - Creates `hf_home` directory.
    - If running as root (`os.getuid() == 0`), calls `_update_ownership` on `hf_home` to ensure the non-root `appuser` (used in Docker) can write to it.

### _update_ownership Workflow
1.  Checks if `appuser` exists via `id appuser`.
2.  Applies `chown -R --silent appuser:appgroup` to each path.
3.  Verifies write access by executing `test -w` as `appuser` via `gosu`.
4.  If verification fails, applies `chmod -R 775` as a fallback.

# Goal
The prompt file provides sufficient detail to regenerate `utils.py`, including the system-level ownership management logic, VRAM querying via `nvidia-smi`, and the suite of strict path validation helpers.
