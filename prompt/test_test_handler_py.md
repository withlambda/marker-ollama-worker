# `test/test-handler.py`

## Context
This script mocks the RunPod handler execution logic to test it locally without a serverless environment.

## Logic
1.  **Mocking**:
    *   Mocks `runpod.serverless.start()` to avoid network calls or actual serverless loop.
2.  **Environment**:
    *   Assumes `handler.py` is in the same directory (or path accessible via `sys.path`).
3.  **Functions**:
    *   `test_handler()`:
        *   Defines a sample job payload (dict) mimicking RunPod event structure.
        *   Calls `handler(job)` directly.
        *   Prints result.
        *   Verifies if the result status is "completed" and message matches expected success string.
        *   Exits with status 0 on success, 1 on failure.
4.  **Execution**:
    *   Runs `test_handler()` if executed as a script.
