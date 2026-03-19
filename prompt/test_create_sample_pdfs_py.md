# Context
This script, `test/create-sample-pdfs.py`, is a utility to generate mock PDF documents for testing purposes. It is typically called by `test/run.sh` to ensure there is input data available for the integration test.

# Interface

## Main Functions

### `create_pdf(filename, text)`
Creates a single-page PDF with a string of text at a fixed coordinate.
- **Dependencies**: `reportlab.pdfgen.canvas`.
- **Arguments**:
  - `filename` (str): Output path.
  - `text` (str): Content to render.

### `main()`
Orchestrates the creation of multiple sample PDFs.
- **Environment Variables**:
  - `TEST_INPUT_DIR`: The directory where the PDFs will be saved.
- **Logic**:
  - Creates the `TEST_INPUT_DIR` if it doesn't exist.
  - Generates `test1.pdf` and `test2.pdf` with simple identifying text.

# Logic
The script uses the `reportlab` library to programmatically create PDFs. It is a lightweight alternative to copying real, potentially large, PDFs into the repository for testing.

# Goal
The prompt file provides the PDF generation logic and dependency requirements to recreate the sample data generator exactly.
