# Marker-PDF with Ollama worker (For RunPod Serverless)

This project provides a Dockerized solution for running `marker-pdf` with `Ollama` LLM support as a **RunPod Serverless Worker**. It is designed to process documents (PDF, DOCX, PPTX, etc.) on-demand, leveraging RunPod's GPU infrastructure.

## Architecture

The container runs a Python handler script that listens for jobs from the RunPod API. When a job is received, it:
1.  **Model Setup**:
    *   If `OLLAMA_MODEL` is set, it checks if the model exists locally (pulling it from the Ollama registry if necessary).
    *   If `OLLAMA_MODEL` is *not* set, it attempts to **build** an Ollama model from a cached Hugging Face GGUF file (specified by `OLLAMA_HUGGING_FACE_MODEL_NAME` and `OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION`).
2.  **Processing**: Processes the specified input file or directory using `marker-pdf` (and `marker` for other formats).
3.  **Cleanup**: Deletes the input file upon successful processing.
4.  **Result**: Returns the result (status, processed files, errors).

## Features

*   **Serverless Worker**: Fully compatible with RunPod Serverless.
*   **Multi-Format Support**: Supports `.pdf`, `.pptx`, `.docx`, `.xlsx`, `.html`, and `.epub`.
*   **Ollama Integration**: Leverages a local Ollama instance for enhanced OCR and conversion.
*   **Offline/Cached Models**: Can build Ollama models dynamically from a mounted Hugging Face cache, avoiding repeated network downloads.
*   **NVIDIA Optimized**: Uses the official `pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime` base image for maximum GPU performance.
*   **Configurable**: Job inputs can override default environment variables.

## Prerequisites

*   Docker
*   RunPod Account

## Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/your-username/marker-ollama-worker.git
    cd marker-ollama-worker
    ```

2.  Build the Docker image:
    ```bash
    docker build -t marker-ollama-worker .
    ```

3.  Push the image to a container registry (e.g., Docker Hub, GHCR).

## Model Management

### Ollama model

This worker supports two methods for managing Ollama models:

#### 1. Pull from Cached Ollama Registry (via mounted volume)
Set the `OLLAMA_MODEL` environment variable (e.g., `llama3`). The worker will attempt to pull this model from the cached Ollama registry if it is not present. Note that the cached registry
must be mounted to the directory path specified by the environment variable `OLLAMA_MODELS_DIR`.

#### 2. Build from Hugging Face Cache (Offline/Mounted)
If there is access to the hugging face cache, for example via mounted volumes,
a `GGUF` hugging face model available in that hugging face cache can be specified via the two environment variables
`OLLAMA_HUGGING_FACE_MODEL_NAME` (e.g., `Qwen/Qwen3-VL-8B-Thinking-GGUF`) and `OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION` (e.g., `Q4_K_M`). **For this to work, `OLLAMA_MODEL` must be unset**, such that the ollama model itself is generated from the
hugging face model. The hugging face cache must be available under the mounted volume root, specified by `VOLUME_ROOT_MOUNT_PATH` and the `HF_HOME` environment variable must be set accordingly to the cache path.

The worker will look for the GGUF file in `HF_HOME` and create the Ollama model locally before processing.

### Marker/Surya internal models

To prevent that marker starts downloading its own internal Surya models,
the models must be available before the worker starts.
This can be done by either downloading the models locally via

```sh
python3 -c "from marker.models import create_model_dict; create_model_dict()";
```

and then make the whole marker models inside the Docker container available
at `/app/cache/datalab/models`.

Otherwise, if access to a hugging face cache is available, the following environment variables
can be set

```shell
MODEL_CACHE_DIR=<HF_HOME>/hub
DETECTOR_MODEL_CHECKPOINT=karlo0/surya_line_det_2.20
LAYOUT_MODEL_CHECKPOINT=karlo0/surya_layout_multimodal
FOUNDATION_MODEL_CHECKPOINT=karlo0/surya_text_recognition
RECOGNITION_MODEL_CHECKPOINT=karlo0/surya_text_recognition
TABLE_REC_MODEL_CHECKPOINT=karlo0/surya_tablerec
OCR_ERROR_MODEL_CHECKPOINT=karlo0/tarun-menta_ocr_error_detection
```

where `<HF_HOME>` should be the path to the mounted hugging face cache.
Note: The models `karlo0/...` where obtained by downloading the models
directly from marker as described by the above python command and then
re-uploaded to hugging face. This should ensure that exactly the required
models for marker are used.

### Pre-downloading Models
To populate your volume with models, use the utilities provided in `config/download-models`. See [config/download-models/README.md](config/download-models/README.md) for instructions.

## Usage

### RunPod Deployment

1.  **Create a Template**: In RunPod, create a new Serverless Template.
    *   **Image Name**: Your pushed image (e.g., `ghcr.io/your-username/marker-ollama-worker:latest`).
    *   **Container Disk Size**: 20GB (recommended).
    *   **Environment Variables**: Set defaults (see below).

2.  **Create an Endpoint**: Create a new Serverless Endpoint using the template.

### Job Input Format

You can trigger the worker with a JSON payload. `input_dir` and `output_dir` are required fields.

```json
{
  "input": {
    "input_dir": "input/my_document.pdf", 
    "output_dir": "output",
    "output_format": "markdown",
    "marker_workers": 2,
    "marker_paginate_output": false,
    "marker_force_ocr": false,
    "marker_disable_multiprocessing": false,
    "marker_disable_image_extraction": false,
    "marker_page_range": "0-10",
    "marker_processors": "marker.processors.images.ImageProcessor",
    "ollama_block_correction_prompt": "Optional custom prompt"
  }
}
```

#### Core Parameters

*   `input_dir`: **Required**. The path to the file or directory to process, relative to `VOLUME_ROOT_MOUNT_PATH`. Supported formats: PDF, PPTX, DOCX, XLSX, HTML, EPUB.
*   `output_dir`: **Required**. The directory where the processed output will be saved, relative to `VOLUME_ROOT_MOUNT_PATH`.
*   `output_format`: (Optional) The format for the output results. Supported options: `markdown`, `json`, `html`, `chunks`. Default: `markdown`.

#### Marker Processing Parameters

*   `marker_workers`: (Optional) Number of PDFs to process in parallel. Default: auto-calculated based on available VRAM and file count.
*   `marker_paginate_output`: (Optional) Boolean. If true, outputs will be paginated. Default: `false`.
*   `marker_force_ocr`: (Optional) Boolean. If true, forces OCR even if text is present. Default: `false`.
*   `marker_disable_multiprocessing`: (Optional) Boolean. If true, disables multiprocessing (sets `pdftext_workers` to 1). Default: `false`.
*   `marker_disable_image_extraction`: (Optional) Boolean. If true, disables the extraction of images from the document. Default: `false`.
*   `marker_page_range`: (Optional) A string specifying the page range to convert. Can be comma-separated numbers or ranges (e.g., "0,5-10,20").
*   `marker_processors`: (Optional) A comma-separated string of processors to use. Must use the full module path (e.g., `marker.processors.images.ImageProcessor`).

#### LLM Post-Processing Parameters

*   `ollama_block_correction_prompt`: (Optional) A custom prompt string to use for block correction with the LLM. Takes priority over `block_correction_prompt_key`.
*   `block_correction_prompt_key`: (Optional) A key referencing a predefined prompt from the [Block Correction Prompt Catalog](#block-correction-prompt-catalog). Ignored if `ollama_block_correction_prompt` is provided.
*   `ollama_chunk_workers`: (Optional) Number of text chunks to process in parallel during LLM phase. Overrides `OLLAMA_CHUNK_WORKERS` env var. Default: auto-calculated.

#### Performance Tuning Examples

**Example 1: Single Large PDF (500 pages)**
```json
{
  "input": {
    "input_dir": "input/large_book.pdf",
    "output_dir": "output",
    "ollama_chunk_workers": 4
  }
}
```
This maximizes chunk-level parallelism for faster LLM processing of large documents.

**Example 2: Batch of Small PDFs**
```json
{
  "input": {
    "input_dir": "input/batch/",
    "output_dir": "output",
    "marker_workers": 4
  }
}
```
This processes multiple files in parallel through the Marker phase.

**Example 3: Conservative Settings (Low VRAM)**
```json
{
  "input": {
    "input_dir": "input/",
    "output_dir": "output",
    "marker_workers": 1,
    "ollama_chunk_workers": 1
  }
}
```
For GPUs with <16GB VRAM, disable parallelization to prevent OOM errors.

### Block Correction Prompt Catalog

The worker includes a built-in catalog of specialized OCR correction prompts optimized for different document types and languages. Instead of providing a full custom prompt, you can reference a predefined prompt by its key.

**Prompt File Location:** [`block_correction_prompts.json`](block_correction_prompts.json)

#### How to Use

**Option 1: Use a Predefined Prompt (Recommended)**
```json
{
  "input": {
    "input_dir": "input/fraktur_book.pdf",
    "output_dir": "output",
    "block_correction_prompt_key": "fraktur_german_19c"
  }
}
```

**Option 2: Provide a Custom Prompt**
```json
{
  "input": {
    "input_dir": "input/document.pdf",
    "output_dir": "output",
    "ollama_block_correction_prompt": "Your custom prompt here..."
  }
}
```

**Priority:** If both `ollama_block_correction_prompt` and `block_correction_prompt_key` are provided, the custom prompt (`ollama_block_correction_prompt`) takes priority.

#### Available Prompt Keys

| Key | Name | Description |
|:----|:-----|:------------|
| `fraktur_german_19c` | 19th Century German (Fraktur/Gothic Script) | Historical German texts in Fraktur font with archaic orthography. Preserves 'th', 'y', 'c', long-s (ſ), and handles visual confusions. |
| `english_handwriting` | English Handwriting (Modern Cursive) | Modern English cursive/script documents. Corrects connected letters, ambiguous letterforms, and stroke variations. |
| `german_handwriting` | German Handwriting (Modern Cursive) | Modern German cursive/script, including Sütterlin influence. Handles umlauts, ß, and German ligatures. |
| `french_handwriting` | French Handwriting (Modern Cursive) | Modern French cursive/script. Restores accents (é, è, ê, à, ç), handles elisions and French orthography. |
| `spanish_handwriting` | Spanish Handwriting (Modern Cursive) | Modern Spanish cursive/script. Handles accents (á, é, í, ó, ú), ñ, and inverted punctuation (¿¡). |
| `modern_english_general` | Modern English (General Purpose) | Standard modern English printed documents. Fixes common OCR errors and layout artifacts. |
| `scientific_mathematical` | Scientific and Mathematical Texts | Documents with equations, formulas, and technical notation. Reconstructs mathematical expressions and LaTeX notation. |
| `legal_documents` | Legal Documents (Formal Text) | Formal legal texts with precise terminology, enumeration, and structure. Preserves Latin legal terms. |
| `historical_english` | Historical English (Pre-20th Century) | Historical English (16th-19th centuries) with archaic spelling, long-s (ſ), and period grammar. |
| `asian_languages_cjk` | Asian Languages (Chinese, Japanese, Korean) | CJK character recognition with corrections for visually similar characters and mixed scripts. |

#### Usage Examples

**Example 1: 19th Century German Book**
```json
{
  "input": {
    "input_dir": "input/alte_deutsche_buecher/",
    "output_dir": "output",
    "block_correction_prompt_key": "fraktur_german_19c",
    "marker_force_ocr": true
  }
}
```

**Example 2: French Handwritten Letters**
```json
{
  "input": {
    "input_dir": "input/lettres_manuscrites/",
    "output_dir": "output",
    "block_correction_prompt_key": "french_handwriting"
  }
}
```

**Example 3: Scientific Paper with Equations**
```json
{
  "input": {
    "input_dir": "input/research_paper.pdf",
    "output_dir": "output",
    "block_correction_prompt_key": "scientific_mathematical"
  }
}
```

**Example 4: Legal Contract**
```json
{
  "input": {
    "input_dir": "input/contract.pdf",
    "output_dir": "output",
    "block_correction_prompt_key": "legal_documents"
  }
}
```

#### Custom Prompts vs. Catalog

- **Use Catalog Prompts** when your document matches one of the predefined scenarios. These prompts are carefully crafted and tested for specific use cases.
- **Use Custom Prompts** when you need highly specialized correction rules not covered by the catalog, or when you want to experiment with different prompt strategies.
- **Combine Approaches:** Start with a catalog prompt, test the results, then create a custom prompt if needed.

#### Examples for Custom `ollama_block_correction_prompt`

If the predefined catalog prompts don't meet your needs, you can provide a fully custom prompt. Here are some examples to inspire your own custom prompts:

**Custom Prompt Template Structure:**
```text
Role: [Define the expert role/persona]

Task: [Describe the correction task]

Critical Correction Rules:
1. [Rule 1]
2. [Rule 2]
3. [Rule 3]
...

Output Formatting: Provide ONLY the corrected text in clean Markdown.
```

**Note:** For most use cases, we recommend using the [Block Correction Prompt Catalog](#block-correction-prompt-catalog) instead of writing custom prompts. The catalog prompts are extensively tested and optimized for their respective scenarios.

### Environment Variables

| Variable                                 | Description                                           | Default                                          |
|:-----------------------------------------|:------------------------------------------------------|:-------------------------------------------------|
| `VOLUME_ROOT_MOUNT_PATH`                 | Base path for storage (Required).                     | **None** (Must be set)                           |
| `USE_POSTPROCESS_LLM`                    | Enable LLM post-processing.                           | `true`                                           |
| `CLEANUP_OUTPUT_DIR_BEFORE_START`        | Delete output directory before starting.              | `false`                                          |
| `OLLAMA_MODEL`                           | Name of the Ollama model to use/pull.                 | (Optional)                                       |
| `OLLAMA_HUGGING_FACE_MODEL_NAME`         | HF Model ID to build from (if `OLLAMA_MODEL` unset).  | (Required if `OLLAMA_MODEL` unset & LLM enabled) |
| `OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION` | Quantization string to match GGUF file.               | (Required if `OLLAMA_MODEL` unset & LLM enabled) |
| `HF_HOME`                                | Path to Hugging Face cache.                           | `${VOLUME_ROOT_MOUNT_PATH}/huggingface-cache`    |
| `OLLAMA_MODELS_DIR`                      | Directory for Ollama models (relative to root mount). | `/.ollama/models`                                |
| `MARKER_DEBUG`                           | Enable debug mode.                                    | `False`                                          |

### Performance Tuning Variables

The worker includes adaptive parallelization to maximize GPU utilization (optimized for 24GB VRAM). These settings are automatically calculated based on workload, but can be manually overridden.

| Variable                  | Description                                                                                          | Default | Recommended Range |
|:--------------------------|:-----------------------------------------------------------------------------------------------------|:--------|:------------------|
| `TOTAL_VRAM_GB`           | Total VRAM available on your GPU (used for auto-tuning worker counts).                               | `24`    | `8-80`            |
| `OLLAMA_CHUNK_WORKERS`    | Number of text chunks to process in parallel during Ollama LLM phase.                                | `auto`  | `1-4` or `auto`   |
| `OLLAMA_CHUNK_SIZE`       | Characters per chunk for LLM processing. Smaller = more parallelism, larger = better context.        | `4000`  | `2000-8000`       |
| `MARKER_VRAM_PER_WORKER`  | Estimated VRAM per Marker worker (GB). Used for auto-calculating `marker_workers`.                   | `5`     | `3-6`             |
| `OLLAMA_VRAM_PER_WORKER`  | Estimated VRAM per Ollama worker (GB). Used for auto-calculating `OLLAMA_CHUNK_WORKERS`.             | `5`     | `4-8`             |

#### Adaptive Worker Scaling (Auto Mode)

When set to `auto` (default), the worker automatically optimizes parallelism based on:

**Single Large PDF** (1 file):
- `marker_workers=1` (no file-level parallelism needed)
- `OLLAMA_CHUNK_WORKERS=4` (maximize chunk parallelism for large documents)
- **Best for**: Processing 500+ page PDFs efficiently

**Small Batch** (2-3 files):
- `marker_workers=2` (moderate file parallelism)
- `OLLAMA_CHUNK_WORKERS=3-4` (high chunk parallelism)
- **Best for**: Medium workloads with moderate-sized PDFs

**Large Batch** (4+ files):
- `marker_workers=3-4` (maximize marker file parallelism)
- `OLLAMA_CHUNK_WORKERS=3-4` (maximize chunk parallelism, files processed sequentially)
- **Best for**: Batch processing many small-to-medium PDFs

#### Performance Examples

| Scenario                  | Default (Sequential) | Optimized (Adaptive) | Speedup |
|:--------------------------|:---------------------|:---------------------|:--------|
| 1 × 500-page PDF          | ~4.3 min             | ~2.1 min             | **2.0x** |
| 3 × 200-page PDFs         | ~7.5 min             | ~2.8 min             | **2.7x** |
| 10 × 50-page PDFs         | ~15 min              | ~3.9 min             | **3.8x** |

#### Manual Tuning

For specific hardware or workloads, you can override auto-tuning:

```bash
# Example: 48GB VRAM GPU - maximize parallelism
TOTAL_VRAM_GB=48
OLLAMA_CHUNK_WORKERS=6

# Example: 16GB VRAM GPU - conservative settings
TOTAL_VRAM_GB=16
OLLAMA_CHUNK_WORKERS=2

# Example: Disable LLM parallelization (troubleshooting)
OLLAMA_CHUNK_WORKERS=1
```

### Additional Configuration Variables

The following variables can also be set to further customize the environment, though they typically have sensible defaults or are managed internally.

**Surya / Marker Models**

| Variable                       | Description                                                     |
|:-------------------------------|:----------------------------------------------------------------|
| `MODEL_CACHE_DIR`              | Cache directory for models. Default: `/v/huggingface-cache/hub` |
| `DETECTOR_MODEL_CHECKPOINT`    | Detection model checkpoint.                                     |
| `LAYOUT_MODEL_CHECKPOINT`      | Layout model checkpoint.                                        |
| `FOUNDATION_MODEL_CHECKPOINT`  | Foundation model checkpoint.                                    |
| `RECOGNITION_MODEL_CHECKPOINT` | Recognition model checkpoint.                                   |
| `TABLE_REC_MODEL_CHECKPOINT`   | Table recognition model checkpoint.                             |
| `OCR_ERROR_MODEL_CHECKPOINT`   | OCR error detection model checkpoint.                           |

**Tools / Performance**

| Tool             | Variable                      | Description                                  | Default                  |
|:-----------------|:------------------------------|:---------------------------------------------|:-------------------------|
| **Python**       | `PYTHONUNBUFFERED`            | Force unbuffered stdout/stderr.              | `1`                      |
| **Hugging Face** | `HF_HUB_OFFLINE`              | Run Hugging Face Hub in offline mode.        | `1`                      |
| **Ollama**       | `OLLAMA_BASE_URL`             | Base URL for Ollama server.                  | `http://127.0.0.1:11434` |
| **PyTorch**      | `PYTORCH_ENABLE_MPS_FALLBACK` | Fallback to CPU if MPS ops aren't supported. | `1`                      |
| **PyTorch**      | `TORCH_NUM_THREADS`           | Threads for intraop parallelism on CPU.      | `1`                      |
| **PyTorch**      | `OMP_NUM_THREADS`             | Threads for OpenMP parallel regions.         | `1`                      |
| **PyTorch**      | `MKL_NUM_THREADS`             | Threads for Intel MKL library.               | `1`                      |
| **PyTorch**      | `TORCH_DEVICE`                | Device to use (`cpu`, `cuda`, `mps`).        | Auto-detected            |

**Marker Specific**

| Variable              | Description                               |
|:----------------------|:------------------------------------------|
| `BASE_DIR`            | Base directory for marker operations.     |
| `OUTPUT_ENCODING`     | Encoding for output text (e.g., `utf-8`). |
| `OUTPUT_IMAGE_FORMAT` | Format for output images (e.g., `JPEG`).  |

## Local Testing

You can test the handler logic locally using the provided test scripts.

1.  **Run the Test**:
    The `test/run.sh` script sets up a local environment and runs the handler with a sample payload.
    ```bash
    cd test
    ./run.sh
    ```

## Development

### Coding Style

This project follows a specific formatting style for Python function definitions:
-   Functions with **zero or one parameter** are defined on a single line.
-   Functions with **two or more parameters** wrap each parameter to its own line with a **4-space continuation indent** for better readability.

**Single-line Example (0-1 parameters):**
```python
def simple_function(param1: str) -> bool:
    return True
```

**Multi-line Example (2+ parameters):**
```python
def complex_function(
    param1: str,
    param2: int = 10,
    param3: Optional[bool] = None
) -> bool:
    # Function body
    return True
```

This style is documented and manually maintained, with `.editorconfig` providing foundational settings (like indentation and charset) compatible with IntelliJ IDEA.

### .editorconfig

An `.editorconfig` file is provided at the root of the project to ensure consistent formatting across different editors and IDEs. Key settings include:
-   UTF-8 charset
-   LF line endings
-   4-space standard indentation for Python.
-   4-space continuation indentation for parameters on new lines.
-   Consistent formatting for Python (manual wrapping for 2+ parameters with 4-space indent).

## Releasing

To release a new version of the project, use the `release.sh` script. This script updates the version in `VERSION` and `requirements.txt`, generates a changelog, commits the changes, creates a git tag, and pushes everything to the remote repository.

```bash
./release.sh <new_version>
```

Example:
```bash
./release.sh 1.10.3
```

This will trigger the GitHub Action to build and push the Docker image with the new version tag.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

[GNU General Public License v3.0](LICENSE)
