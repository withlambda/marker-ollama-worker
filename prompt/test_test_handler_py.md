# Context
This script, `test/test-handler.py`, is a unit/integration test for the main `handler` function. it mocks the `runpod` environment to allow for local execution of the handler logic within a Docker container or development environment.

# Interface

## Main Functions

### `test_handler()`
Simulates a RunPod job and invokes the handler.
- **Logic**:
  - Mocks `runpod.serverless.start` to prevent the worker from entering an infinite loop.
  - Defines a sample `job` payload with `input_dir`, `output_dir`, and various `marker_*` and `vllm_*` setting overrides.
  - Calls `handler(job)` directly.
  - Inspects the returned JSON for `status: "completed"` and a success message referencing the `VOLUME_ROOT_MOUNT_PATH`.
  - Exits with code 0 on success, or 1 on failure/exception.

# Logic
The script is designed to be run inside the test container built by `test/run.sh`. It verifies that the `handler` can correctly parse input, initialize the configuration, and orchestrate the conversion process for a set of input files.

# Goal
The prompt file provides the structure and mocking strategy required to recreate the handler test script, ensuring that the main processing entry point can be verified in a controlled local environment.
