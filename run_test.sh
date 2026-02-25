#!/bin/bash

# Script to run local tests for the Dockerized Marker-PDF solution.

# --- Configuration ---
TEST_INPUT_DIR="test_data/input"
TEST_OUTPUT_DIR="test_data/output"
DOCKER_COMPOSE_FILE="docker-compose.test.yml"

# --- 1. Check for Sample PDFs ---

echo "Checking for sample PDFs in $TEST_INPUT_DIR..."

if [ ! -d "$TEST_INPUT_DIR" ] || [ -z "$(ls -A "$TEST_INPUT_DIR")" ]; then
    echo "Sample PDFs not found. Generating them..."
    python3 create_sample_pdfs.py
    if [ $? -ne 0 ]; then
        echo "Error: Failed to generate sample PDFs."
        exit 1
    fi
else
    echo "Sample PDFs found."
fi

# --- 2. Build Docker Image ---

echo "Building Docker image..."
docker-compose -f "$DOCKER_COMPOSE_FILE" build
if [ $? -ne 0 ]; then
    echo "Error: Failed to build Docker image."
    exit 1
fi

# --- 3. Run Container ---

echo "Running container..."
# Run in detached mode first to ensure services start, or just run up
# Since the container is designed to exit after processing, 'up' is fine.
# We use --abort-on-container-exit to stop if the container exits (which it should).
docker-compose -f "$DOCKER_COMPOSE_FILE" up --abort-on-container-exit

EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo "Error: Container exited with non-zero status."
    # Don't exit immediately, check output first.
fi

# --- 4. Verify Output ---

echo "Verifying output in $TEST_OUTPUT_DIR..."

# Check if output directory exists
if [ ! -d "$TEST_OUTPUT_DIR" ]; then
    echo "Error: Output directory not found."
    exit 1
fi

# Check for Markdown files
MD_FILES=$(find "$TEST_OUTPUT_DIR" -name "*.md")

if [ -z "$MD_FILES" ]; then
    echo "FAILURE: No Markdown files generated."
    exit 1
else
    echo "SUCCESS: Markdown files generated:"
    echo "$MD_FILES"
fi

echo "Test completed successfully."
exit 0
