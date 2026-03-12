# `entrypoint/run-handler.sh`

## Context
This script executes the Python handler script as the `appuser` user. It is the final step in the container's startup sequence.

## Logic
1.  **Execute**:
    *   Prints "Starting RunPod Handler...".
    *   Executes `python3 -u "${HANDLER_FILE_NAME}"` as `appuser` using `gosu`.
    *   The `-u` flag ensures unbuffered output for immediate logging.
    *   This script assumes `HANDLER_FILE_NAME` is set (e.g., `handler.py`).

## Environment Variables
*   `HANDLER_FILE_NAME` (Optional, Default: `handler.py`)
