# Marker-PDF with Ollama worker (For RunPod Serverless)

This project provides a Dockerized solution for running `marker-pdf` with `Ollama` LLM support as a **RunPod Serverless Worker**. It is designed to process documents (PDF, DOCX, PPTX, etc.) on-demand, leveraging RunPod's GPU infrastructure.

## Architecture

The container runs a Python handler script that listens for jobs from the RunPod API. When a job is received, it:
1.  **Model Setup**:
    *   If `OLLAMA_MODEL` is set, it checks if the model exists locally (pulling it from the Ollama registry if necessary).
    *   If `OLLAMA_MODEL` is *not* set, it attempts to **build** an Ollama model from a cached Hugging Face GGUF file (specified by `OLLAMA_HUGGING_FACE_MODEL_NAME` and `OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION`).
2.  **Processing**: Processes the specified input directory using `marker-pdf` (and `marker` for other formats).
3.  **Cleanup**: Deletes the input file upon successful processing (optional).
4.  **Result**: Returns the result (status, processed files, errors).

### Process Architecture

When running `ps aux` inside the container, you may observe multiple processes:

#### Python Processes
There are typically two processes named `python3 -u handler.py`. This is standard behavior for the RunPod serverless environment and the `multiprocessing` library:
*   **Supervisor/Manager**: One process acts as the supervisor, handling RunPod API communication and job distribution. It has a minimal memory footprint (approx. 500MB) as it does not load the heavy ML models.
*   **Active Worker**: The other process is the active worker that performs the document conversion. This process loads the models into memory (e.g., ~23GB RSS) and handles the CPU/GPU intensive tasks.

This dual-process architecture provides isolation; the supervisor remains responsive even if a worker process encounters a critical failure (like a segfault or Out-of-Memory error). Both processes share the same command name because they are initialized using the `spawn` start method, which is required for safe CUDA operations.

#### Ollama Processes
When LLM post-processing is enabled, you will see two `ollama` processes:
*   **Ollama Server**: This is the main orchestrator (`ollama serve`) that manages model loading and provides the API.
*   **Ollama Runner**: This is a child process spawned by the server to perform the actual inference. It typically has a larger memory footprint (RES) as it contains the model weights in VRAM (or RAM if falling back to CPU).

**Note:** If you see an `ollama` process with extremely high CPU usage (e.g., > 1000%), it usually indicates that the model is running on the CPU instead of the GPU. This worker includes the necessary GPU runners to avoid this, but it may still happen if VRAM is insufficient.

## Features

*   **Serverless Worker**: Fully compatible with RunPod Serverless.
*   **Multi-Format Support**: Supports `.pdf`, `.pptx`, `.docx`, `.xlsx`, `.html`, and `.epub`.
*   **Ollama Integration**: Leverages a local Ollama instance for enhanced OCR and conversion.
*   **Offline/Cached Models**: Can build Ollama models dynamically from a mounted Hugging Face cache, avoiding repeated network downloads.
*   **NVIDIA Optimized**: Uses the official `pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime` base image for maximum GPU performance.
*   **Configurable**: Job inputs can override default environment variables.

### VRAM Management

The worker is designed to maximize GPU utilization while avoiding Out-of-Memory (OOM) errors. It follows a two-phase processing model:
1.  **Marker Phase**: Documents are converted to the target format. Marker models (Surya, etc.) are loaded into VRAM.
2.  **Ollama Phase**: If post-processing is enabled, Marker models are moved to CPU and the CUDA cache is cleared to provide Ollama with full access to the VRAM.

This ensures that Ollama can load large LLMs into VRAM even if the Marker models previously consumed most of the available memory. For the next job, Marker models are moved back to GPU as needed.

### Troubleshooting GPU Usage

If you suspect Ollama is running on RAM (CPU) instead of VRAM (GPU), check the following:

1.  **VRAM Logs**: Look for `VRAM Usage (After Marker)` in the worker logs. If `Free` memory is low (e.g., < 2GB) before Ollama starts, it may fallback to CPU. The current version of this worker automatically frees up VRAM before Ollama starts.
2.  **Ollama Debugging**: Set the environment variable `OLLAMA_DEBUG=1`. This will log detailed information from the Ollama server to the container's standard output (and `ollama.log`), including which layers were loaded onto the GPU.
3.  **Model Size**: Ensure your chosen model fits in the available VRAM. A 7B model usually requires ~5-8GB depending on quantization.
4.  **GPU Visibility**: Check the `Environment Info` section at the start of the logs to verify that `CUDA_VISIBLE_DEVICES` is correctly set and `nvidia-smi` is accessible.

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
must be mounted to the directory path specified by the environment variable `OLLAMA_MODELS`.

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

You can trigger the worker with a JSON payload. `input_dir` and `output_dir` are required fields. `input_dir` must be a directory containing the files to process.

**Note on Ollama Configuration:** Any configuration variable for the Ollama worker can be overridden in the job input by prefixing it with `ollama_`. For example, `ollama_context_length` overrides `OLLAMA_CONTEXT_LENGTH`. See the [Ollama Configuration](#ollama-configuration-overrides) section for a full list of supported keys.

```json
{
  "input": {
    "input_dir": "input/documents/", 
    "output_dir": "output",
    "output_format": "markdown",
    "marker_workers": 2,
    "marker_paginate_output": false,
    "marker_force_ocr": false,
    "marker_disable_multiprocessing": false,
    "marker_disable_image_extraction": false,
    "marker_page_range": "0-10",
    "marker_processors": "marker.processors.images.ImageProcessor",
    "delete_input_on_success": false,
    "ollama_block_correction_prompt": "Optional custom prompt",
    "ollama_chunk_workers": 2,
    "ollama_image_description_prompt": "Optional custom prompt for image descriptions"
  }
}
```

#### Core Parameters

*   `input_dir`: **Required**. The path to the directory to process, relative to `VOLUME_ROOT_MOUNT_PATH` (absolute paths are also supported). The directory must contain one or more files in supported formats: PDF, PPTX, DOCX, XLSX, HTML, EPUB.
*   `output_dir`: **Required**. The directory where the processed output will be saved, relative to `VOLUME_ROOT_MOUNT_PATH` (absolute paths are also supported).
*   `output_format`: (Optional) The format for the output results. Supported options: `markdown`, `json`, `html`, `chunks`. Default: `markdown`. **Note**: LLM post-processing on `json` and `html` formats is experimental and may produce invalid syntax due to text chunking.
*   `delete_input_on_success`: (Optional) Boolean. If true, deletes input files after they have been successfully processed. Default: `false`.

#### LLM Post-Processing Parameters

*   `ollama_block_correction_prompt`: (Optional) A custom prompt string to use for block correction with the LLM. Takes priority over `block_correction_prompt_key`.
*   `block_correction_prompt_key`: (Optional) A key referencing a predefined prompt from the [Block Correction Prompt Catalog](#block-correction-prompt-catalog). Ignored if `ollama_block_correction_prompt` is provided.
*   `ollama_chunk_workers`: (Optional) Number of parallel workers for chunk processing and image description generation. Default: auto-calculated.
*   `ollama_image_description_prompt`: (Optional) Custom prompt for extracted image descriptions. If omitted, a built-in factual vision prompt is used.

When marker image extraction is enabled, the LLM post-processing phase also describes each extracted image and inserts the descriptions directly into text outputs (`.md`/`.txt`), ideally placed immediately following their corresponding image tags. To ensure clarity for LLMs like NotebookLM or AnythingLM, these descriptions are wrapped in explicit `[BEGIN IMAGE DESCRIPTION]` and `[END IMAGE DESCRIPTION]` markers. If a matching tag cannot be found, the descriptions are appended as a fallback section at the end of the file. Non-text outputs are left unchanged.

#### Marker Configuration Overrides

The following `marker_`-prefixed keys can be used in the `input` section of the job payload to override processing settings for a specific job:

| Key                               | Description                                                     | Default    |
|:----------------------------------|:----------------------------------------------------------------|:-----------|
| `marker_workers`                  | Number of PDFs to process in parallel.                          | `auto`     |
| `marker_paginate_output`          | Whether to paginate the output text.                            | `false`    |
| `marker_force_ocr`                | Force OCR even if text is present.                              | `false`    |
| `marker_disable_multiprocessing`  | Disable internal multiprocessing (sets `pdftext_workers` to 1). | `false`    |
| `marker_disable_image_extraction` | Disable extraction of images from documents.                    | `false`    |
| `marker_page_range`               | Page range to convert (e.g., "0,5-10").                         | `None`     |
| `marker_processors`               | Comma-separated list of marker processors to run.               | `None`     |
| `marker_output_format`            | The format of the output (markdown, json, etc.).                | `markdown` |
| `marker_maxtasksperchild`         | Tasks per worker before recycling (prevents memory leaks).      | `10`       |

#### Ollama Configuration Overrides

The following `ollama_`-prefixed keys can be used in the `input` section of the job payload to override server and client settings for a specific job:

| Key                               | Description                                                |
|:----------------------------------|:-----------------------------------------------------------|
| `ollama_host`                     | Base URL for the Ollama server (alias: `ollama_base_url`). |
| `ollama_model`                    | Name of the Ollama model to use.                           |
| `ollama_context_length`           | Context window size (tokens).                              |
| `ollama_num_parallel`             | Max parallel requests for the server.                      |
| `ollama_keep_alive`               | Duration to keep models in memory (e.g., `-1`).            |
| `ollama_flash_attention`          | Enable/disable Flash Attention (`1` or `0`).               |
| `ollama_kv_cache_type`            | Quantization for K/V cache (e.g., `q8_0`).                 |
| `ollama_max_retries`              | Max retries for LLM requests.                              |
| `ollama_retry_delay`              | Delay (seconds) between retries.                           |
| `ollama_chunk_size`               | Characters per text chunk (default: `4000`).               |
| `ollama_debug`                    | Enable Ollama server debug logging (`1`).                  |
| `ollama_log_dir`                  | Directory for `ollama.log`.                                |
| `ollama_hf_model_name`            | HF model to build from if `ollama_model` is unset.         |
| `ollama_hf_model_quantization`    | HF quantization string for building.                       |
| `ollama_max_loaded_models`        | Max models loaded concurrently.                            |
| `ollama_max_queue`                | Max number of queued requests.                             |
| `ollama_image_description_prompt` | Custom prompt for image descriptions.                      |

#### Performance Tuning Examples

**Example 1: Single Large PDF (500 pages)**
```json
{
  "input": {
    "input_dir": "input/",
    "output_dir": "output",
    "ollama_chunk_workers": 4
  }
}
```
This maximizes chunk-level parallelism for faster LLM processing of large documents. (Note: `input/` should contain the single PDF file).

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

| Key                       | Name                                        | Description                                                                                                                            |
|:--------------------------|:--------------------------------------------|:---------------------------------------------------------------------------------------------------------------------------------------|
| `fraktur_german_19c`      | 19th Century German (Fraktur/Gothic Script) | Historical German texts in Fraktur font with archaic orthography. Preserves 'th', 'y', 'c', long-s (ſ), and handles visual confusions. |
| `english_handwriting`     | English Handwriting (Modern Cursive)        | Modern English cursive/script documents. Corrects connected letters, ambiguous letterforms, and stroke variations.                     |
| `german_handwriting`      | German Handwriting (Modern Cursive)         | Modern German cursive/script, including Sütterlin influence. Handles umlauts, ß, and German ligatures.                                 |
| `french_handwriting`      | French Handwriting (Modern Cursive)         | Modern French cursive/script. Restores accents (é, è, ê, à, ç), handles elisions and French orthography.                               |
| `spanish_handwriting`     | Spanish Handwriting (Modern Cursive)        | Modern Spanish cursive/script. Handles accents (á, é, í, ó, ú), ñ, and inverted punctuation (¿¡).                                      |
| `modern_english_general`  | Modern English (General Purpose)            | Standard modern English printed documents. Fixes common OCR errors and layout artifacts.                                               |
| `scientific_mathematical` | Scientific and Mathematical Texts           | Documents with equations, formulas, and technical notation. Reconstructs mathematical expressions and LaTeX notation.                  |
| `legal_documents`         | Legal Documents (Formal Text)               | Formal legal texts with precise terminology, enumeration, and structure. Preserves Latin legal terms.                                  |
| `historical_english`      | Historical English (Pre-20th Century)       | Historical English (16th-19th centuries) with archaic spelling, long-s (ſ), and period grammar.                                        |
| `asian_languages_cjk`     | Asian Languages (Chinese, Japanese, Korean) | CJK character recognition with corrections for visually similar characters and mixed scripts.                                          |

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

The worker can be configured using environment variables. For `OllamaSettings` and `MarkerSettings`, properties can be set using the `OLLAMA_` or `MARKER_` prefix respectively (e.g., `MARKER_WORKERS`, `OLLAMA_CONTEXT_LENGTH`).

| Variable                                 | Description                                                | Default                                          |
|:-----------------------------------------|:-----------------------------------------------------------|:-------------------------------------------------|
| `VOLUME_ROOT_MOUNT_PATH`                 | Base path for storage (Required).                          | **None** (Must be set)                           |
| `USE_POSTPROCESS_LLM`                    | Enable LLM post-processing for the output results.         | `true`                                           |
| `CLEANUP_OUTPUT_DIR_BEFORE_START`        | Delete output directory before starting.                   | `false`                                          |
| `OLLAMA_MODEL`                           | Name of the Ollama model to use/pull.                      | (Optional)                                       |
| `OLLAMA_HUGGING_FACE_MODEL_NAME`         | HF Model ID to build from (if `OLLAMA_MODEL` unset).       | (Required if `OLLAMA_MODEL` unset & LLM enabled) |
| `OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION` | Quantization string to match GGUF file.                    | (Required if `OLLAMA_MODEL` unset & LLM enabled) |
| `OLLAMA_CONTEXT_LENGTH`                  | Context window length (tokens) per request.                | `4096`                                           |
| `OLLAMA_VRAM_FACTOR`                     | VRAM (GB) per token for context calculation.               | `0.00013`                                        |
| `OLLAMA_IMAGE_DESCRIPTION_PROMPT`        | Default prompt template for extracted image descriptions.  | (Optional)                                       |
| `HF_HOME`                                | Path to Hugging Face cache.                                | `${VOLUME_ROOT_MOUNT_PATH}/huggingface-cache`    |
| `OLLAMA_MODELS`                          | Absolute path to Ollama models directory.                  | `${VOLUME_ROOT_MOUNT_PATH}/.ollama/models`       |
| `OLLAMA_LOG_DIR`                         | Absolute path to Ollama logs directory.                    | `${VOLUME_ROOT_MOUNT_PATH}/.ollama/logs`         |
| `MARKER_DEBUG`                           | Enable debug mode.                                         | `False`                                          |
| `MARKER_WORKERS`                         | Number of Marker workers (env-level default).              | `auto`                                           |
| `MARKER_PAGINATE_OUTPUT`                 | Whether to paginate output (env-level default).            | `false`                                          |
| `MARKER_FORCE_OCR`                       | Force OCR even if text is present.                         | `false`                                          |
| `MARKER_DISABLE_MULTIPROCESSING`         | Disable internal Marker multiprocessing.                   | `false`                                          |
| `MARKER_DISABLE_IMAGE_EXTRACTION`        | Disable extraction of images.                              | `false`                                          |
| `MARKER_PAGE_RANGE`                      | Default page range to convert.                             | `None`                                           |
| `MARKER_PROCESSORS`                      | Default processors to run.                                 | `None`                                           |
| `MARKER_OUTPUT_FORMAT`                   | Default output format (markdown, json, etc.).              | `markdown`                                       |
| `MARKER_MAXTASKSPERCHILD`                | Tasks per worker before recycling (prevents memory leaks). | `10`                                             |

### Performance Tuning Variables

The worker includes adaptive parallelization to maximize GPU utilization (optimized for 24GB VRAM). These settings are automatically calculated based on workload but can be manually overridden.

| Variable                 | Description                                                                                      | Default   | Recommended Range |
|:-------------------------|:-------------------------------------------------------------------------------------------------|:----------|:------------------|
| `TOTAL_VRAM_GB`          | Total VRAM available on your GPU (used for auto-tuning worker counts).                           | `24`      | `8-80`            |
| `OLLAMA_CHUNK_SIZE`      | Characters per chunk for LLM processing. Smaller = more parallelism, larger = better context.    | `4000`    | `2000-8000`       |
| `MARKER_VRAM_PER_WORKER` | Estimated VRAM per Marker worker (GB). Used for auto-calculating `marker_workers`.               | `5`       | `3-6`             |
| `OLLAMA_CONTEXT_LENGTH`  | Context length (tokens) per request. Used for auto-calculating `OLLAMA_NUM_PARALLEL`.            | `4096`    | `2048-32768`      |
| `OLLAMA_VRAM_FACTOR`     | VRAM (GB) per token. Used for auto-calculating `OLLAMA_NUM_PARALLEL` (default: 0.00013).         | `0.00013` | `0.0001-0.0005`   |
| `OLLAMA_BASE_VRAM_GB`    | Estimated VRAM (GB) for the base model weights. Used for auto-calculating `OLLAMA_NUM_PARALLEL`. | `8`       | `2-16`            |
| `OLLAMA_MAX_RETRIES`     | Maximum retries for LLM chunk processing on transient/recoverable errors.                        | `3`       | `1-10`            |
| `OLLAMA_RETRY_DELAY`     | Base delay (seconds) for exponential backoff between retries.                                    | `2.0`     | `1.0-5.0`         |
| `OLLAMA_NUM_PARALLEL`    | Max parallel requests per model (auto-set to `ollama_chunk_workers` if unset).                   | `auto`    | `1-8`             |
| `OLLAMA_FLASH_ATTENTION` | Enable Flash Attention for improved memory efficiency.                                           | `1`       | `0, 1`            |
| `OLLAMA_KV_CACHE_TYPE`   | Quantization type for K/V cache (e.g., `f16`, `q8_0`, `q4_0`).                                   | `f16`     | `f16, q8_0, q4_0` |
| `OLLAMA_MAX_QUEUE`       | Maximum number of queued requests before rejection.                                              | `512`     | `100-2048`        |
| `OLLAMA_KEEP_ALIVE`      | How long models stay in memory after a request (e.g., `5m`, `1h`, `-1` for infinite).            | `-1`      | `0`, `5m`, `-1`   |

#### Adaptive Worker Scaling (Auto Mode)

When set to `auto` (default), the worker automatically optimizes parallelism based on:

**Ollama Concurrency**:
- `OLLAMA_NUM_PARALLEL` is calculated based on available VRAM and context window size:
  `parallel = floor((TOTAL_VRAM - VRAM_RESERVE - OLLAMA_BASE_VRAM) / (OLLAMA_VRAM_FACTOR * OLLAMA_CONTEXT_LENGTH))`
- `ollama_chunk_workers` (Python threads) is set to a high default (16) to ensure Ollama's internal request queue stays saturated, maximizing GPU throughput.

**Marker Concurrency**:
- `marker_workers` is scaled based on number of files and available VRAM (capped at 4).

**Processing Scenarios**:

**Single File** (1 file):
- `marker_workers=1` (no file-level parallelism needed)
- `ollama_chunk_workers` (high thread count to saturate queue)
- **Best for**: Processing single large PDFs efficiently

**Small Batch** (2-3 files):
- `marker_workers` (moderate file parallelism, up to 2)
- `ollama_chunk_workers` (high chunk parallelism, capped at 4)
- **Best for**: Medium workloads with moderate-sized PDFs

**Large Batch** (4+ files):
- `marker_workers` (maximize marker file parallelism, up to 4)
- `ollama_chunk_workers` (maximize chunk parallelism, files processed sequentially)
- **Best for**: Batch processing many small-to-medium PDFs

*Note: All auto-calculations are bounded by available VRAM (TOTAL_VRAM_GB).*

#### Performance Examples

| Scenario          | Default (Sequential) | Optimized (Adaptive) | Speedup  |
|:------------------|:---------------------|:---------------------|:---------|
| 1 × 500-page PDF  | ~4.3 min             | ~2.1 min             | **2.0x** |
| 3 × 200-page PDFs | ~7.5 min             | ~2.8 min             | **2.7x** |
| 10 × 50-page PDFs | ~15 min              | ~3.9 min             | **3.8x** |

#### Manual Tuning

For specific hardware or workloads, you can override auto-tuning:

```bash
# Example: 48GB VRAM GPU, medium LLM models - maximize parallelism
TOTAL_VRAM_GB=48
OLLAMA_CONTEXT_LENGTH=8192

# Example: 16GB VRAM GPU, small LLM models - conservative settings
TOTAL_VRAM_GB=16
OLLAMA_BASE_VRAM_GB=4

# Example: Disable LLM parallelization via "ollama_chunk_workers=1" in json input of serverless endpoint (troubleshooting)
ollama_chunk_workers=1
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

| Tool             | Variable                          | Description                                       | Default                  |
|:-----------------|:----------------------------------|:--------------------------------------------------|:-------------------------|
| **Python**       | `PYTHONUNBUFFERED`                | Force unbuffered stdout/stderr.                   | `1`                      |
| **Hugging Face** | `HF_HUB_OFFLINE`                  | Run Hugging Face Hub in offline mode.             | `1`                      |
| **Ollama**       | `OLLAMA_HOST`                     | Base URL for Ollama server.                       | `http://127.0.0.1:11434` |
| **Ollama**       | `OLLAMA_DEBUG`                    | Enable Ollama server debug logging (`1`).         | `0`                      |
| **Ollama**       | `OLLAMA_IMAGE_DESCRIPTION_PROMPT` | Prompt template for extracted image descriptions. | (Optional)               |
| **Ollama**       | `OLLAMA_MAX_LOADED_MODELS`        | Max models loaded concurrently.                   | `3 * GPUs`               |
| **Ollama**       | `OLLAMA_KEEP_ALIVE`               | Duration to keep models loaded in memory.         | `-1`                     |
| **Ollama**       | `OLLAMA_MODELS`                   | Directory where Ollama models are stored.         | (Managed internally)     |
| **PyTorch**      | `PYTORCH_ENABLE_MPS_FALLBACK`     | Fallback to CPU if MPS ops aren't supported.      | `1`                      |
| **PyTorch**      | `TORCH_NUM_THREADS`               | Threads for intraop parallelism on CPU.           | `1`                      |
| **PyTorch**      | `OMP_NUM_THREADS`                 | Threads for OpenMP parallel regions.              | `1`                      |
| **PyTorch**      | `MKL_NUM_THREADS`                 | Threads for Intel MKL library.                    | `1`                      |
| **PyTorch**      | `TORCH_DEVICE`                    | Device to use (`cpu`, `cuda`, `mps`).             | Auto-detected            |

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

You can release a new version of the project either locally or via a GitHub Workflow. The process automates versioning, changelog generation, and Docker image publishing.

### Using GitHub Workflow (Recommended)

1.  Navigate to the **Actions** tab in the GitHub repository.
2.  Select the **Release** workflow from the sidebar.
3.  Click **Run workflow**.
4.  Enter the new version number (e.g., `1.10.3`), optionally enable `dry_run`, and click **Run workflow**.

This workflow will:
- Update the version in `VERSION` and `requirements.txt`.
- Generate a `CHANGELOG.md` entry from recent commits.
- Commit the changes and create a git tag.
- Push the changes and the tag to the repository.
- **Trigger the Docker publish workflow** automatically as a subsequent step.

### Using local script (Alternative)

Alternatively, you can use the `release.sh` script locally:

```bash
./release.sh [-d|--dry-run] <version>
```

Example:
```bash
./release.sh 1.10.3
```

The script performs the following:
1.  **Validates** the version format (X.Y.Z).
2.  **Checks** for uncommitted changes and existing tags.
3.  **Normalizes** the version (strips 'v' prefix if present).
4.  **Updates** the `VERSION` file and `requirements.txt` (`marker-pdf` version).
5.  **Generates** a `CHANGELOG.md` entry based on git commits since the last tag.
6.  **Commits**, tags, and pushes to the current branch.

After the tag is pushed locally, the **Docker** GitHub Action will be triggered by the tag push event.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

[GNU General Public License v3.0](LICENSE)
