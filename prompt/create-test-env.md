# Create Local Testing Environment (RunPod Serverless)

## Goal
Set up a local testing environment to verify the functionality of the Dockerized `marker-pdf` solution in its **RunPod Serverless** configuration.

## Functionality
The setup should:
1.  Create a directory structure for testing (input/output).
2.  Generate two simple, lightweight PDF files for testing purposes.
3.  Provide a `docker-compose.test.yml` file configured to run the container locally.
4.  Include a script `test_handler.py` that simulates a RunPod job event and invokes the handler logic.

## Implementation Details
-   **Directory Structure**:
    -   `test_data/input`: Directory for input PDF files.
    -   `test_data/output`: Directory for generated Markdown files.
-   **Sample PDFs**:
    -   Create two minimal PDF files (e.g., using a Python script with `reportlab` or `fpdf`) containing simple text.
    -   Save them as `test1.pdf` and `test2.pdf` in `test_data/input`.
-   **Docker Compose**:
    -   Set necessary environment variables (e.g., `OLLAMA_MODEL`).
    -   **CPU Support**: Ensure the `docker-compose.test.yml` does *not* require NVIDIA runtime or GPU resources. It should be configured to run on CPU by default for testing.
    -   Ensure the container is built from the local `Dockerfile`.
-   **Verification**:
    -   Create a simple shell script `run_test.sh` that:
        1.  Checks if `test_data/input` exists and contains PDF files. If not, runs `create_sample_pdfs.py`.
        2.  Builds the Docker image using `docker-compose -f docker-compose.test.yml build`.
        3.  Runs the container using `docker-compose -f docker-compose.test.yml up`.
        4.  **Note**: Since the container runs a serverless handler, it might wait for a job. The test script should ideally send a request to the local endpoint if RunPod SDK supports it, or simply verify that the container starts up correctly and processes the default input if configured to do so on start (or via a test flag).
        5.  Alternatively, `test_handler.py` can be run *inside* the container to test the logic directly. Let's use `docker-compose run` to execute `python3 test_handler.py` inside the container environment.

## Output
Generate the following files:
1.  `create_sample_pdfs.py`: Python script to generate the sample PDF files.
2.  `docker-compose.test.yml`: Docker Compose file for testing (CPU-compatible).
3.  `test_handler.py`: A Python script that imports the handler function (or mocks the event loop) and calls it with a sample job payload to verify processing.
4.  `run_test.sh`: Shell script to execute the test (build image, run `test_handler.py` inside container).
5.  `README_TEST.md`: Instructions on how to use the testing environment.

## License

[GNU General Public License v3.0](../LICENSE)
