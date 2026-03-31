# NoteLM - MinerU + vLLM
Use MinerU with vLLM in a docker container to run on serverless GPU cloud instances.
Current support is for serverless instance on runpod.io.

This project provides a Dockerized solution for running `MinerU` with `vLLM` LLM support as a **RunPod Serverless Worker**. It is designed to process documents (PDF, DOCX, PPTX, etc.) on-demand, leveraging RunPod's GPU infrastructure.

## Architecture

The container runs a Python handler script that listens for jobs from the RunPod API. When a job is received, it:
1.  **MinerU Phase**: Processes the specified input directory using `MinerU` for document conversion (OCR, visual layout analysis, etc.).
2.  **vLLM Phase**: If LLM post-processing is enabled, starts a vLLM server subprocess, waits for readiness via health-check polling, and processes converted text through the model for OCR error correction and image descriptions.
3.  **Cleanup**: Deletes the input file upon successful processing (optional).
4.  **Result**: Returns the result:
    -   `status`: `completed`, `partially_completed` (if some files failed post-processing), or `success` (if no files were found).
    -   `message`: A summary description of the outcome.
    -   `failures`: (Optional) A list of filenames that failed during the vLLM post-processing phase. In the event of a critical vLLM server failure, this will contain the specific error message to help diagnostics.

### Process Architecture

When running `ps aux` inside the container, you may observe multiple processes:

#### Python Processes
There are typically two processes named `python3 -u handler.py`. This is standard behavior for the RunPod serverless environment and the `multiprocessing` library:
*   **Supervisor/Manager**: One process acts as the supervisor, handling RunPod API communication and job distribution. It has a minimal memory footprint (approx. 500MB) as it does not load the heavy ML models.
*   **Active Worker**: The other process is the active worker that performs the document conversion. This process loads the models into memory (e.g., ~23GB RSS) and handles the CPU/GPU intensive tasks.

This dual-process architecture provides isolation; the supervisor remains responsive even if a worker process encounters a critical failure (like a segfault or Out-of-Memory error). Both processes share the same command name because they are initialized using the `spawn` start method, which is required for safe CUDA operations.

#### vLLM Process
When LLM post-processing is enabled, the handler spawns a vLLM server subprocess (`vllm serve`):
*   The server is started after MinerU processing completes and VRAM is freed.
*   A health-check endpoint (`GET /health`) is polled until the server is ready.
*   Communication uses the OpenAI-compatible API via the `openai` Python client.
*   After all post-processing is complete, the server is gracefully shut down (SIGTERM → wait 10s → SIGKILL).
*   If the server crashes mid-processing, one automatic restart is attempted before failing the job.

## Features

*   **Serverless Worker**: Fully compatible with RunPod Serverless.
*   **Multi-Format Support**: Supports `.pdf`, `.pptx`, `.docx`, `.xlsx`, `.html`, and `.epub` (via MinerU).
*   **vLLM Integration**: Leverages a local vLLM server subprocess for high-performance LLM inference via an OpenAI-compatible API.
*   **Language-Aware Image Descriptions**: Automatically detects the document language (per-file) and generates image descriptions in that language using localized Markdown wrappers (supports English, German, French, Spanish, Italian, Portuguese, Dutch, Polish, Czech, and Russian).
*   **Token Precision**: Integrates `tiktoken` for accurate context window utilization during text chunking.
*   **Local Model Weights**: Loads models directly from a local directory (`NOTELM_VLLM_MODEL_PATH`), avoiding runtime downloads.
*   **NVIDIA Optimized**: Uses the official `pytorch/pytorch:2.10.0-cuda12.8-cudnn9-runtime` base image for maximum GPU performance.
*   **Configurable**: Job inputs can override default environment variables.

### VRAM Management

The worker is designed to maximize GPU utilization while avoiding Out-of-Memory (OOM) errors. It follows a two-phase processing model:
1.  **MinerU Phase**: Documents are converted to the target format. MinerU models are loaded into VRAM.
2.  **vLLM Phase**: After MinerU completes, CUDA cache is cleared and a configurable VRAM recovery delay (`NOTELM_VLLM_VRAM_RECOVERY_DELAY`) ensures GPU memory is fully released before vLLM starts.

The vLLM worker implements robust error handling, including exponential backoff and automatic server restarts, for both text correction and image description tasks.

This sequential execution model ensures that vLLM has full access to VRAM for loading and serving the LLM.

### Troubleshooting GPU Usage

1.  **VRAM Logs**: Look for `VRAM Usage (After MinerU)` in the worker logs. If `Free` memory is low (e.g., < 2GB) before vLLM starts, increase `NOTELM_VLLM_VRAM_RECOVERY_DELAY` or reduce `NOTELM_VLLM_GPU_UTIL`.
2.  **Model Size**: Ensure your chosen model fits in the available VRAM with the configured `NOTELM_VLLM_GPU_UTIL` fraction. A 7B model usually requires ~5-8GB depending on quantization.
3.  **GPU Visibility**: Check the `Environment Info` section at the start of the logs to verify that `CUDA_VISIBLE_DEVICES` is correctly set and `nvidia-smi` is accessible.
4.  **vLLM Server Logs**: The vLLM subprocess stdout/stderr is captured and logged. Check for OOM errors or CUDA-related failures in the worker logs.
5.  **Triton JIT Compiler**: vLLM/Triton compiles CUDA helper modules at runtime. The container must keep a C/C++ compiler (`gcc`/`g++`) available, otherwise startup can fail with `RuntimeError: Failed to find C compiler`.
6.  **Python C Headers**: Triton also compiles Python extension glue code and requires `Python.h` at runtime. Keep Python development headers installed in the image (e.g., `python3-dev` for the container Python version), otherwise startup can fail with `fatal error: Python.h: No such file or directory`.

## Prerequisites

*   Docker
*   RunPod Account

## Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/your-username/notelm-mineru-worker.git
    cd notelm-mineru-worker
    ```

2.  Build the Docker image:
    ```bash
    docker build -t notelm-mineru .
    ```

    *Note:* The build environment includes all necessary dependencies for both MinerU and vLLM.

3.  Push the image to a container registry (e.g., Docker Hub, GHCR).

## Model Management

### vLLM Model

vLLM loads model weights directly from a local directory specified by `NOTELM_VLLM_MODEL_PATH`. The model name for API calls is either set explicitly via `NOTELM_VLLM_MODEL` or derived automatically from the directory name.

For the model to work:
- `NOTELM_VLLM_MODEL_PATH` must point to a directory containing the model weights (e.g., SafeTensors format).
- The model must fit within the available VRAM (controlled by `NOTELM_VLLM_GPU_UTIL` and `NOTELM_VLLM_VRAM_GB_MODEL`).
- The Hugging Face cache should be mounted under the path specified by `HF_HOME` for any tokenizer or config files.

### MinerU Model Management

To prevent MinerU from downloading its models at runtime, they must be available locally. The models are configured via a `mineru.json` configuration file, pointed to by the `MINERU_TOOLS_CONFIG_PATH` environment variable.

**Example `mineru.json`:**
```json
{
  "models-dir": "/app/models/mineru"
}
```

The configuration ensures that all OCR and layout models are loaded from the specified baked-in or mounted directory.

### Pre-downloading Models
To populate your volume with models, use the utilities provided in `config/download-models`. See [config/download-models/README.md](config/download-models/README.md) for instructions.

## Usage

### RunPod Deployment

1.  **Create a Template**: In RunPod, create a new Serverless Template.
    *   **Image Name**: Your pushed image (e.g., `ghcr.io/your-username/notelm-mineru-worker:latest`).
    *   **Container Disk Size**: 20GB (recommended).
    *   **Environment Variables**: Set defaults (see below).

2.  **Create an Endpoint**: Create a new Serverless Endpoint using the template.

### Job Input Format

You can trigger the worker with a JSON payload. `input_dir` and `output_dir` are required fields. `input_dir` must be a directory containing the files to process.

**Note on vLLM Configuration:** Any configuration variable for the vLLM worker can be overridden in the job input by prefixing it with `vllm_`. For example, `vllm_chunk_size` overrides `NOTELM_VLLM_CHUNK_SIZE`. See the [vLLM Configuration](#vllm-configuration-overrides) section for a full list of supported keys.

```json
{
  "input": {
    "input_dir": "input/documents/", 
    "output_dir": "output",
    "output_format": "markdown",
    "mineru_workers": 2,
    "mineru_ocr_mode": "ocr",
    "mineru_page_range": "0-10",
    "mineru_disable_image_extraction": false,
    "delete_input_on_success": false,
    "vllm_block_correction_prompt": "Optional custom prompt",
    "vllm_chunk_workers": 2,
    "vllm_image_description_prompt": "Optional custom prompt for image descriptions"
  }
}
```

#### Core Parameters

*   `input_dir`: **Required**. The path to the directory to process, relative to `VOLUME_ROOT_MOUNT_PATH` (absolute paths are also supported). The directory must contain one or more files in supported formats: PDF, PPTX, DOCX, XLSX, HTML, EPUB.
*   `output_dir`: **Required**. The directory where the processed output will be saved, relative to `VOLUME_ROOT_MOUNT_PATH` (absolute paths are also supported).
*   `output_format`: (Optional) The format for the output results. Supported options: `markdown`, `json`, `html`, `chunks`. Default: `markdown`. **Note**: LLM post-processing on `json` and `html` formats is experimental and may produce invalid syntax due to text chunking.
*   `delete_input_on_success`: (Optional) Boolean. If true, deletes input files after they have been successfully processed. Default: `false`.

#### LLM Post-Processing Parameters

*   `vllm_block_correction_prompt`: (Optional) A custom prompt string to use for block correction with the LLM. Takes priority over `vllm_block_correction_prompt_key`.
*   `vllm_block_correction_prompt_key`: (Optional) A key referencing a predefined prompt from the [Block Correction Prompt Catalog](#block-correction-prompt-catalog). Ignored if `vllm_block_correction_prompt` is provided.
*   `vllm_chunk_workers`: (Optional) Number of parallel async tasks for chunk processing and image description generation. Default: 16.
*   `vllm_image_description_prompt`: (Optional) Custom prompt for extracted image descriptions. If omitted, a built-in book scan analysis prompt is used.

When MinerU image extraction is enabled, the LLM post-processing phase also describes each extracted image and inserts the descriptions directly into text outputs (`.md`/`.txt`), ideally placed immediately following their corresponding image tags. To ensure clarity for LLMs like NotebookLM or AnythingLM, these descriptions are wrapped in explicit `[BEGIN IMAGE DESCRIPTION]` and `[END IMAGE DESCRIPTION]` markers. If a matching tag cannot be found, the descriptions are appended as a fallback section at the end of the file. Non-text outputs are left unchanged.

#### MinerU Configuration Overrides

The following `mineru_`-prefixed keys can be used in the `input` section of the job payload to override processing settings for a specific job:

| Key                               | Description                                                     | Default    |
|:----------------------------------|:----------------------------------------------------------------|:-----------|
| `mineru_workers`                  | Number of documents to process in parallel.                     | `auto`     |
| `mineru_ocr_mode`                 | OCR mode for PDF parsing (`auto`, `txt`, `ocr`).                | `auto`     |
| `mineru_page_range`               | Page range to convert (e.g., "0-10").                           | `None`     |
| `mineru_disable_image_extraction` | Disable image extraction and removal of `images` subfolder.     | `false`    |
| `mineru_output_format`            | The format of the output (always `markdown`).                   | `markdown` |
| `mineru_maxtasksperchild`         | Tasks per worker before recycling (prevents memory leaks).      | `25`       |
| `mineru_disable_maxtasksperchild` | Disable automatic recycling of tasks for the child process.     | `false`    |

#### vLLM Configuration Overrides

The following `vllm_`-prefixed keys can be used in the `input` section of the job payload to override server and client settings for a specific job:

| Key                                | Description                                                                                                                                                                                                                                       |
|:-----------------------------------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `vllm_model`                       | Model name for API calls (derived from path if unset).                                                                                                                                                                                            |
| `vllm_host`                        | Host IP where vLLM server runs.                                                                                                                                                                                                                   |
| `vllm_port`                        | Port for the vLLM server.                                                                                                                                                                                                                         |
| `vllm_gpu_util`                    | Maximum GPU memory fraction for vLLM (0.0–1.0).                                                                                                                                                                                                   |
| `vllm_max_model_len`               | Maximum context/sequence length (tokens); completion tokens are auto-capped to remaining context, and effective chunk input is reduced by prompt-token usage.                                                                                     |
| `vllm_max_num_seqs`                | Max concurrent sequences (auto-calculated from VRAM).                                                                                                                                                                                             |
| `vllm_startup_timeout`             | Seconds to wait for vLLM health check on startup.                                                                                                                                                                                                 |
| `vllm_vram_recovery_delay`         | Seconds to wait after MinerU before starting vLLM.                                                                                                                                                                                                |
| `vllm_max_retries`                 | Max retries for LLM requests.                                                                                                                                                                                                                     |
| `vllm_retry_delay`                 | Delay (seconds) between retries.                                                                                                                                                                                                                  |
| `vllm_chunk_size`                  | Tokens per text chunk (default: `4000`). Markdown-structure-aware; effective chunk size is auto-reduced by prompt-token usage and context safety margin; oversized blocks are split into non-overlapping chunks using `langchain-text-splitters`. |
| `vllm_chunk_workers`               | Async tasks for parallel chunk processing.                                                                                                                                                                                                        |
| `vllm_block_correction_prompt_key` | Key into the block correction prompt catalog.                                                                                                                                                                                                     |
| `vllm_block_correction_prompt`     | Custom block correction prompt override.                                                                                                                                                                                                          |
| `vllm_image_description_prompt`    | Custom prompt for image descriptions.                                                                                                                                                                                                             |

#### Performance Tuning Examples

**Example 1: Single Large PDF (500 pages)**
```json
{
  "input": {
    "input_dir": "input/",
    "output_dir": "output",
    "vllm_chunk_workers": 4
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
    "mineru_workers": 4
  }
}
```
This processes multiple files in parallel through the MinerU phase.

**Example 3: Conservative Settings (Low VRAM)**
```json
{
  "input": {
    "input_dir": "input/",
    "output_dir": "output",
    "mineru_workers": 1,
    "vllm_chunk_workers": 1
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
    "vllm_block_correction_prompt": "Your custom prompt here..."
  }
}
```

**Priority:** If both `vllm_block_correction_prompt` and `vllm_block_correction_prompt_key` are provided, the custom prompt (`vllm_block_correction_prompt`) takes priority.

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
    "mineru_force_ocr": true
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

#### Examples for Custom `vllm_block_correction_prompt`

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

The worker can be configured using environment variables. For `VllmSettings`, use official vLLM names where available (`NOTELM_VLLM_HOST`, `NOTELM_VLLM_PORT`) and `NOTELM_VLLM_*` names for worker-specific settings; `MinerUSettings` uses `MINERU_*`. Legacy `VLLM_*` worker-specific names are still accepted for backward compatibility.

| Variable                                   | Description                                                                                                                                                                                                               | Default                                       |
|:-------------------------------------------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:----------------------------------------------|
| `VOLUME_ROOT_MOUNT_PATH`                   | Base path for storage (Required).                                                                                                                                                                                         | **None** (Must be set)                        |
| `VRAM_GB_TOTAL`                            | Total VRAM available on your GPU (Required).                                                                                                                                                                              | **None** (Must be set)                        |
| `VRAM_GB_RESERVE`                          | VRAM to reserve for system/other processes (GB).                                                                                                                                                                          | `4`                                           |
| `USE_POSTPROCESS_LLM`                      | Enable LLM post-processing for the output results.                                                                                                                                                                        | `true`                                        |
| `CLEANUP_OUTPUT_DIR_BEFORE_START`          | Delete output directory before starting.                                                                                                                                                                                  | `false`                                       |
| `NOTELM_VLLM_MODEL_PATH`                  | Path to model weights on disk (Required).                                                                                                                                                                                 | **None** (Must be set)                        |
| `NOTELM_VLLM_MODEL`                       | Model name for API calls (derived from path if unset).                                                                                                                                                                    | (Optional)                                    |
| `NOTELM_VLLM_VRAM_GB_MODEL`               | VRAM consumed by the model in GB (Required).                                                                                                                                                                              | **None** (Must be set)                        |
| `NOTELM_VLLM_HOST`                        | Host IP where vLLM server runs.                                                                                                                                                                                           | `127.0.0.1`                                   |
| `NOTELM_VLLM_PORT`                        | Port for the vLLM server.                                                                                                                                                                                                 | `8001`                                        |
| `NOTELM_VLLM_GPU_UTIL`                    | Maximum GPU memory fraction for vLLM (0.0–1.0).                                                                                                                                                                           | `0.85`                                        |
| `NOTELM_VLLM_MAX_MODEL_LEN`               | Maximum context/sequence length (tokens); chunk completion tokens are auto-capped to remaining context and chunk input is reduced by prompt-token usage.                                                                  | `16384`                                        |
| `NOTELM_VLLM_MAX_NUM_SEQS`                | Max concurrent sequences (auto-calculated from VRAM).                                                                                                                                                                     | `16`                                          |
| `NOTELM_VLLM_STARTUP_TIMEOUT`             | Seconds to wait for vLLM health check on startup.                                                                                                                                                                         | `120`                                         |
| `NOTELM_VLLM_VRAM_RECOVERY_DELAY`         | Seconds to wait after MinerU before starting vLLM.                                                                                                                                                                        | `10`                                          |
| `NOTELM_VLLM_CPU`                         | Run vLLM on CPU (for testing/non-GPU environments).                                                                                                                                                                       | `false`                                       |
| `NOTELM_VLLM_MAX_RETRIES`                 | Maximum retries for failed API calls.                                                                                                                                                                                     | `3`                                           |
| `NOTELM_VLLM_RETRY_DELAY`                 | Delay between retries in seconds.                                                                                                                                                                                         | `2.0`                                         |
| `NOTELM_VLLM_CHUNK_SIZE`                  | Size of text chunks in tokens for correction phase; effective chunk size is reduced by prompt-token usage/context safety margin; oversized blocks are split into non-overlapping chunks using `langchain-text-splitters`. | `4000`                                        |
| `NOTELM_VLLM_CHUNK_WORKERS`               | Async tasks for parallel chunk processing.                                                                                                                                                                                | `16`                                          |
| `NOTELM_VLLM_IMAGE_DESCRIPTION_PROMPT`    | Custom prompt for extracted image descriptions.                                                                                                                                                                           | (Optional)                                    |
| `NOTELM_VLLM_BLOCK_CORRECTION_PROMPT_KEY` | Key into the block correction prompt catalog.                                                                                                                                                                             | (Optional)                                    |
| `NOTELM_VLLM_BLOCK_CORRECTION_PROMPT`     | Custom block correction prompt override.                                                                                                                                                                                  | (Optional)                                    |
| `BLOCK_CORRECTION_PROMPT_FILE_NAME`        | Filename for the prompt catalog JSON.                                                                                                                                                                                     | `block_correction_prompts.json`               |
| `IMAGE_DESCRIPTION_SECTION_HEADING`        | Heading for the fallback image description section.                                                                                                                                                                       | `## Extracted Image Descriptions`             |
| `IMAGE_DESCRIPTION_HEADING`                | Marker at the beginning of an image description.                                                                                                                                                                          | `**[BEGIN IMAGE DESCRIPTION]**`               |
| `IMAGE_DESCRIPTION_END`                    | Marker at the end of an image description.                                                                                                                                                                                | `**[END IMAGE DESCRIPTION]**`                 |
| `HF_HOME`                                  | Path to Hugging Face cache.                                                                                                                                                                                               | `${VOLUME_ROOT_MOUNT_PATH}/huggingface-cache` |
| `MINERU_DEBUG`                             | Enable debug mode.                                                                                                                                                                                                        | `False`                                       |
| `MINERU_WORKERS`                           | Number of MinerU workers (env-level default).                                                                                                                                                                             | `auto`                                        |
| `MINERU_FORCE_OCR`                         | Force OCR even if text is present.                                                                                                                                                                                        | `false`                                       |
| `MINERU_PAGE_RANGE`                        | Default page range to convert.                                                                                                                                                                                            | `None`                                        |
| `MINERU_OUTPUT_FORMAT`                     | Default output format (markdown, json, etc.).                                                                                                                                                                             | `markdown`                                    |
| `MINERU_MAXTASKSPERCHILD`                  | Tasks per worker before recycling (prevents memory leaks).                                                                                                                                                                | `25`                                          |
| `MINERU_DISABLE_MAXTASKSPERCHILD`          | Disable automatic recycling of tasks for the child process.                                                                                                                                                               | `false`                                       |
| `MINERU_TOOLS_CONFIG_PATH`                 | Path to `mineru.json` configuration file.                                                                                                                                                                                 | `/app/mineru.json`                            |

### Performance Tuning Variables

The worker includes adaptive parallelization to maximize GPU utilization (optimized for 24GB VRAM). These settings are automatically calculated based on workload but can be manually overridden.

| Variable                     | Description                                                                                  | Default    | Recommended Range |
|:-----------------------------|:---------------------------------------------------------------------------------------------|:-----------|:------------------|
| `VRAM_GB_TOTAL`              | Total VRAM available on your GPU (Required).                                                 | **None**   | `8-80`            |
| `VRAM_GB_RESERVE`            | VRAM to reserve for system/other processes (GB).                                             | `4`        | `1-8`             |
| `NOTELM_VLLM_CHUNK_SIZE`    | Tokens per chunk for LLM processing. Smaller = more parallelism, larger = better context.    | `4000`     | `2000-8000`       |
| `MINERU_VRAM_GB_PER_WORKER`  | Estimated VRAM per MinerU worker (GB). Used for auto-calculating `mineru_workers`.           | `5`        | `3-6`             |
| `NOTELM_VLLM_MAX_MODEL_LEN` | Max context/sequence length (tokens). Used for auto-calculating `NOTELM_VLLM_MAX_NUM_SEQS`. | `16384`     | `2048-32768`      |
| `VRAM_GB_PER_TOKEN_FACTOR`   | VRAM (GB) per token. Used for auto-calculating `NOTELM_VLLM_MAX_NUM_SEQS`.                  | `0.00013`  | `0.0001-0.0005`   |
| `NOTELM_VLLM_VRAM_GB_MODEL` | VRAM (GB) consumed by the model. Used for auto-calculating `NOTELM_VLLM_MAX_NUM_SEQS`.      | (Required) | `2-16`            |
| `NOTELM_VLLM_MAX_RETRIES`   | Maximum retries for LLM chunk processing on transient/recoverable errors.                    | `3`        | `1-10`            |
| `NOTELM_VLLM_RETRY_DELAY`   | Base delay (seconds) for exponential backoff between retries.                                | `2.0`      | `1.0-5.0`         |
| `NOTELM_VLLM_MAX_NUM_SEQS`  | Max concurrent sequences (auto-calculated from VRAM if unset).                               | `16`       | `1-32`            |
| `NOTELM_VLLM_GPU_UTIL`      | Maximum GPU memory fraction for vLLM.                                                        | `0.85`     | `0.5-0.95`        |

#### Adaptive Worker Scaling (Auto Mode)

When set to `auto` (default), the worker automatically optimizes parallelism based on:

**vLLM Concurrency**:
- `NOTELM_VLLM_MAX_NUM_SEQS` is calculated based on available VRAM and context window size:
  `max_num_seqs = floor((TOTAL_VRAM - VRAM_RESERVE - NOTELM_VLLM_VRAM_GB_MODEL) / (VRAM_GB_PER_TOKEN_FACTOR * NOTELM_VLLM_MAX_MODEL_LEN))`
- **Precise Token Counting**: Uses the `tiktoken` library to accurately measure chunk sizes for OpenAI-compatible models, ensuring optimal context window utilization.
- `vllm_chunk_workers` (async tasks) defaults to 16, controlling parallel chunk processing.
- The vLLM server is started as a subprocess and monitored via a health check endpoint with a configurable startup timeout (`NOTELM_VLLM_STARTUP_TIMEOUT`).

**MinerU Concurrency**:
- `mineru_workers` is scaled based on number of files and available VRAM (capped at 4).

**Processing Scenarios**:

**Single File** (1 file):
- `mineru_workers=1` (no file-level parallelism needed)
- `vllm_chunk_workers` for parallel chunk processing
- **Best for**: Processing single large PDFs efficiently

**Small Batch** (2-3 files):
- `mineru_workers` (moderate file parallelism, up to 2)
- `vllm_chunk_workers` for parallel chunk processing
- **Best for**: Medium workloads with moderate-sized PDFs

**Large Batch** (4+ files):
- `mineru_workers` (maximize MinerU file parallelism, up to 4)
- `vllm_chunk_workers` for parallel chunk processing (files processed sequentially)
- **Best for**: Batch processing many small-to-medium PDFs

*Note: All auto-calculations are bounded by available VRAM (VRAM_GB_TOTAL).*

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
VRAM_GB_TOTAL=48
NOTELM_VLLM_MAX_MODEL_LEN=16384

# Example: 16GB VRAM GPU, small LLM models - conservative settings
VRAM_GB_TOTAL=16
NOTELM_VLLM_VRAM_GB_MODEL=4

# Example: Disable LLM parallelization via "vllm_chunk_workers=1" in json input of serverless endpoint (troubleshooting)
vllm_chunk_workers=1
```

### Recommended Environment Variables for ~24GB VRAM GPU Deployment

The following environment variables are recommended for a cloud deployment with a single GPU and approximately 24GB VRAM. This configuration balances performance with stability for typical document processing workloads.

| Variable                           | Tool              | Description                                                                                     | Recommended Value                                                       |
|:-----------------------------------|:------------------|:------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------|
| `VOLUME_ROOT_MOUNT_PATH`           | Worker            | Base path for storage volume.                                                                   | `/workspace` (runpod.io pod) or `/runpod-volume` (runpod.io serverless) |
| `VRAM_GB_TOTAL`                    | Worker            | Total VRAM available on the GPU.                                                                | `24`                                                                    |
| `VRAM_GB_RESERVE`                  | Worker            | VRAM to reserve for system/other processes (GB).                                                | `4`                                                                     |
| `USE_POSTPROCESS_LLM`              | Worker            | Enable LLM post-processing for output results.                                                  | `true`                                                                  |
| `CLEANUP_OUTPUT_DIR_BEFORE_START`  | Worker            | Delete output directory before starting new job.                                                | `false`                                                                 |
| `NOTELM_VLLM_MODEL_PATH`          | vLLM              | Path to model weights on disk (e.g., `/workspace/models/mistral-7b-instruct`).                  | (set to your model path, this or `NOTELM_VLLM_MODEL` is required)      |
| `NOTELM_VLLM_MODEL`               | vLLM              | Model name for API calls (auto-derived from path if unset).                                     | (this or `NOTELM_VLLM_MODEL_PATH` is required)                         |
| `NOTELM_VLLM_VRAM_GB_MODEL`       | vLLM              | VRAM consumed by the model in GB (7B model ~6-8GB).                                             | model dependent                                                         |
| `NOTELM_VLLM_HOST`                | vLLM              | Host IP where vLLM server runs.                                                                 | `127.0.0.1`                                                             |
| `NOTELM_VLLM_PORT`                | vLLM              | Port for the vLLM server.                                                                       | `8001`                                                                  |
| `NOTELM_VLLM_GPU_UTIL`            | vLLM              | Maximum GPU memory fraction for vLLM (0.0–1.0).                                                 | `0.85`                                                                  |
| `NOTELM_VLLM_MAX_MODEL_LEN`       | vLLM              | Maximum context/sequence length (tokens).                                                       | `16384`                                                                  |
| `NOTELM_VLLM_MAX_NUM_SEQS`        | vLLM              | Max concurrent sequences (auto-calculated if unset).                                            | `16`                                                                    |
| `NOTELM_VLLM_STARTUP_TIMEOUT`     | vLLM              | Seconds to wait for vLLM health check on startup.                                               | `120`                                                                   |
| `NOTELM_VLLM_VRAM_RECOVERY_DELAY` | vLLM              | Seconds to wait after MinerU before starting vLLM.                                              | `10`                                                                    |
| `HF_HOME`                          | Hugging Face      | Path to Hugging Face cache directory.                                                           | `<VOLUME_ROOT_MOUNT_PATH>/huggingface-cache`                            |
| `HF_HUB_OFFLINE`                   | Hugging Face      | Run Hugging Face Hub in offline mode (prevents downloads).                                      | `1`                                                                     |
| `TRANSFORMERS_OFFLINE`             | Transformers      | Prevents the Transformers library from downloading model weights.                               | `1`                                                                     |
| `MINERU_DEBUG`                     | MinerU            | Enable debug mode for detailed logging.                                                         | `false`                                                                 |
| `MINERU_WORKERS`                   | MinerU            | Number of MinerU workers (auto-calculated if unset).                                            | `auto`                                                                  |
| `MINERU_FORCE_OCR`                 | MinerU            | Force OCR even if text is present.                                                              | `false`                                                                 |
| `MINERU_OUTPUT_FORMAT`             | MinerU            | Default output format (markdown, json, etc.).                                                   | `markdown`                                                              |
| `MINERU_MAXTASKSPERCHILD`          | MinerU            | Tasks per worker before recycling (prevents memory leaks).                                      | `25`                                                                    |
| `MINERU_VRAM_GB_PER_WORKER`        | MinerU            | Estimated VRAM per MinerU worker (GB) for auto-scaling.                                         | `5`                                                                     |
| (x) `PYTORCH_CUDA_ALLOC_CONF`      | PyTorch           | CUDA memory allocator configuration (e.g., `expandable_segments:True` to reduce fragmentation). | `expandable_segments:True`                                              |
| `PYTORCH_ENABLE_MPS_FALLBACK`      | PyTorch           | Fallback to CPU if MPS operations aren't supported.                                             | `1`                                                                     |
| `TORCH_DEVICE`                     | PyTorch           | Device to use (`cpu`, `cuda`, `mps`) - auto-detected if unset.                                  | `cuda`                                                                  |
| `TORCH_NUM_THREADS`                | PyTorch           | Threads for intraop parallelism on CPU.                                                         | `1`                                                                     |
| `OMP_NUM_THREADS`                  | PyTorch           | Threads for OpenMP parallel regions.                                                            | `1`                                                                     |
| `MKL_NUM_THREADS`                  | PyTorch           | Threads for Intel MKL library.                                                                  | `1`                                                                     |
| (x) `NCCL_P2P_DISABLE`             | NCCL/PyTorch      | Disable peer-to-peer GPU communication (set to `1` for single-GPU setups).                      | `1`                                                                     |
| `CUDA_VISIBLE_DEVICES`             | CUDA              | Specifies which GPU(s) to use (0-indexed).                                                      | `0`                                                                     |
| `PYTHONUNBUFFERED`                 | Python            | Force unbuffered stdout/stderr for real-time logging.                                           | `1`                                                                     |
| `OUTPUT_ENCODING`                  | MinerU            | Encoding for output text files.                                                                 | `utf-8`                                                                 |
| `OUTPUT_IMAGE_FORMAT`              | MinerU            | Format for extracted images (JPEG, PNG, etc.).                                                  | `JPEG`                                                                  |
| `VRAM_GB_PER_TOKEN_FACTOR`         | Worker            | VRAM (GB) per token for auto-calculating vLLM concurrency.                                      | `0.00013`                                                               |

**Notes:**

- The environment variables marked with `(x)` should be first checked whether they should be set.
- Set `NOTELM_VLLM_MODEL_PATH` to the absolute path where your model weights are stored.
- Adjust `NOTELM_VLLM_VRAM_GB_MODEL` based on your specific model size (7B models typically use 6-8GB).
- For models with larger context windows (16k+), increase `NOTELM_VLLM_MAX_MODEL_LEN` and reduce `NOTELM_VLLM_MAX_NUM_SEQS`.
- The `MINERU_WORKERS` and `NOTELM_VLLM_MAX_NUM_SEQS` values are auto-calculated based on available VRAM when set to `auto`.
- CPU thread counts (`TORCH_NUM_THREADS`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS`) should be adjusted based on your CPU core count (4 is suitable for 8-16 core systems).
- `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` helps reduce memory fragmentation during long-running jobs.
- `NCCL_P2P_DISABLE=1` is recommended for single-GPU deployments to avoid unnecessary overhead.
- `DTYPE=float16` provides the best balance of speed and accuracy for 24GB VRAM GPUs.

### Additional Configuration Variables

The following variables can also be set to further customize the environment, though they typically have sensible defaults or are managed internally.

**MinerU Models**

| Variable                   | Description                                  |
|:---------------------------|:---------------------------------------------|
| `MINERU_TOOLS_CONFIG_PATH` | Path to `mineru.json` configuration file.    |
| `MINERU_WORKERS`           | Number of MinerU workers (auto-calculated).  |
| `MINERU_VRAM_GB_PER_WORKER`| Estimated VRAM per MinerU worker (GB).       |

**Tools / Performance**

| Tool                    | Variable                                | Description                                                 | Default       |
|:------------------------|:----------------------------------------|:------------------------------------------------------------|:--------------|
| **Python**              | `PYTHONUNBUFFERED`                      | Force unbuffered stdout/stderr.                             | `1`           |
| **Hugging Face**        | `HF_HUB_OFFLINE`                        | Run Hugging Face Hub in offline mode.                       | `1`           |
| **Transformer Library** | `TRANSFORMERS_OFFLINE`                  | Prevents the Transformers library from downloading model weights. | `1`           |
| **vLLM**                | `NOTELM_VLLM_HOST`                     | Host IP where vLLM server runs.                             | `127.0.0.1`   |
| **vLLM**                | `NOTELM_VLLM_PORT`                     | Port for the vLLM server.                                   | `8001`        |
| **vLLM**                | `NOTELM_VLLM_IMAGE_DESCRIPTION_PROMPT` | Prompt template for extracted image descriptions.           | (Optional)    |
| **PyTorch**             | `PYTORCH_ENABLE_MPS_FALLBACK`           | Fallback to CPU if MPS ops aren't supported.                | `1`           |
| **PyTorch**             | `TORCH_NUM_THREADS`                     | Threads for intraop parallelism on CPU.                     | `1`           |
| **PyTorch**             | `OMP_NUM_THREADS`                       | Threads for OpenMP parallel regions.                        | `1`           |
| **PyTorch**             | `MKL_NUM_THREADS`                       | Threads for Intel MKL library.                              | `1`           |
| **PyTorch**             | `TORCH_DEVICE`                          | Device to use (`cpu`, `cuda`, `mps`).                       | Auto-detected |

**MinerU Specific**

| Variable              | Description                               |
|:----------------------|:------------------------------------------|
| `MINERU_OUTPUT_FORMAT`| Default output format (markdown, json).   |
| `OUTPUT_ENCODING`     | Encoding for output text (e.g., `utf-8`). |

## Local Testing

You can test the handler logic locally using the provided test scripts.

1.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run the Test**:
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

### Using a local script (Alternative)

Alternatively, you can use the `release.sh` script locally:

```bash
./release.sh [-d|--dry-run] <version>
```

Example:
```bash
./release.sh 3.0.1
```

The script performs the following:
1.  **Validates** the version format (X.Y.Z).
2.  **Checks** for uncommitted changes and existing tags.
3.  **Normalizes** the version (strips 'v' prefix if present).
4.  **Updates** the `VERSION` file and `requirements.txt`.
5.  **Generates** a `CHANGELOG.md` entry based on git commits since the last tag.
6.  **Commits**, tags, and pushes to the current branch.

After the tag is pushed locally, the **Docker** GitHub Action will be triggered by the tag push event.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

[GNU General Public License v3.0](LICENSE)
