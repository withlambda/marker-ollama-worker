# `test/create-sample-pdfs.py`

## Context
This script generates sample PDF files (`test1.pdf` and `test2.pdf`) for testing purposes, specifically used by the `run.sh` script.

## Logic
1.  **Dependencies**: `reportlab`
2.  **Environment Variables**:
    *   `TEST_INPUT_DIR`: (Required) The directory where the PDFs will be created.
3.  **Functions**:
    *   `create_pdf(filename, text)`: Creates a simple PDF with the given text.
    *   `main()`:
        *   Retrieves `TEST_INPUT_DIR` from environment.
        *   Creates the directory if it doesn't exist.
        *   Calls `create_pdf` to generate two sample PDFs.
4.  **Execution**:
    *   Runs the `main()` function if executed as a script.
