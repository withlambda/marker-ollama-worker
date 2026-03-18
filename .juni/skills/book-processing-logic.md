# Skill: PDF-to-Markdown Enrichment Specialist

## Role
Specialist in post-processing Marker PDF-to-Markdown output: OCR error correction via LLM and multimodal image description. This skill focuses **only** on the processing logic — infrastructure is handled by `vllm-infrastructure.md`, settings by `settings-migration.md`.

## Prerequisites
- `settings-migration.md` must be completed (provides `VllmSettings` with chunk/retry/prompt fields).
- `vllm-infrastructure.md` must be completed (provides vLLM server lifecycle).
- `handler-migration.md` must be completed (provides the updated handler flow).

## Task 1: OCR Error Correction

### Chunking Strategy
1. Split Markdown output into chunks of approximately `chunk_size` **tokens** (default: 4000, configurable via `VLLM_CHUNK_SIZE` env var).
2. Preserve Markdown structure: do not split in the middle of a heading, code block, or table.
3. Process each chunk via the vLLM OpenAI-compatible API for error correction.

### Prompt System
- The project uses a **prompt library** stored in `block_correction_prompts.json` at the project root.
- The prompt to use is selected via:
  - `VLLM_BLOCK_CORRECTION_PROMPT_KEY` — selects a named prompt from the library, **or**
  - `VLLM_BLOCK_CORRECTION_PROMPT` — provides a custom prompt string directly.
- If both are set, the custom prompt takes precedence.
- If neither is set, OCR correction is skipped for that chunk (log a warning).

### API Call Pattern
- Use `openai.AsyncOpenAI(base_url=f"http://localhost:{vllm_port}/v1")`.
- Send each chunk as a user message with the correction prompt as the system message.
- Respect `max_retries` (default: 3) and `retry_delay` (default: 2.0s) from `VllmSettings` on transient failures.

### Concurrency
- Use `chunk_workers` (default: 16, configurable via `VLLM_CHUNK_WORKERS`) async tasks to process chunks in parallel.
- This saturates the vLLM server's request queue for throughput.

## Task 2: Multimodal Vision — Image Descriptions

### Image Detection
- Use the **existing** file-system-based approach from `handler.py`:
  - `list_extracted_images_for_output_file()` scans the output directory for image files (`.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tif`, `.tiff` as defined in `GlobalConfig.IMAGE_FILE_EXTENSIONS`).
  - Do **not** use regex-based Markdown image detection — the existing implementation is more robust.

### Vision Prompt
Use the following prompt when requesting image descriptions from the multimodal vLLM model:

> "Analyze this book scan fragment. Provide a detailed technical description of any diagrams, charts, or illustrations. If it is a photo, describe the subject and context. Output only the description text."

This prompt should be configurable via `VLLM_IMAGE_DESCRIPTION_PROMPT` environment variable.

### Description Injection
- Use the **existing** `insert_image_descriptions_to_text_file()` function from `handler.py`.
- It inserts descriptions using structured markers:
  - `GlobalConfig.image_description_heading` (default: `**[BEGIN IMAGE DESCRIPTION]**`)
  - `GlobalConfig.image_description_end` (default: `**[END IMAGE DESCRIPTION]**`)
- If a dedicated "Image Descriptions" section is needed, it uses `GlobalConfig.image_description_section_heading` (default: `## Extracted Image Descriptions`).
- Do **not** change this format — it is an established contract.

## Task 3: Error Handling & Resilience

### Per-Chunk Error Handling
- If a chunk fails after all retries, log the error and **skip** that chunk (preserve the original uncorrected text).
- Do not fail the entire job because one chunk couldn't be corrected.

### Per-Image Error Handling
- If an image description request fails, log a warning and continue with the next image.
- Insert a placeholder description: `> **Image Description:** [Description unavailable]`.

### Logging
- Log the total number of chunks processed, succeeded, and failed.
- Log the total number of images described, succeeded, and failed.
- Use the existing `logging` module pattern from the codebase.
