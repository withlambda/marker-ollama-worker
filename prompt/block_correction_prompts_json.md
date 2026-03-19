# Context
This file, `block_correction_prompts.json`, serves as a library of specialized system prompts for the LLM post-processing phase. It allows the worker to apply context-aware OCR error correction based on the document's language, script (e.g., Fraktur, Cursive), or domain (e.g., Legal, Scientific).

# Interface

## Structure
The file is a JSON object with a single top-level key: `"prompts"`. This key contains an array of prompt objects.

## Prompt Object Fields
- `key` (string, required): A unique identifier used to select the prompt via environment variables (`VLLM_BLOCK_CORRECTION_PROMPT_KEY`) or job input.
- `name` (string): A human-readable name for the prompt.
- `description` (string): A brief explanation of what the prompt is designed to handle (e.g., "Historical German texts in Fraktur").
- `prompt` (string, required): The actual system prompt text sent to the vLLM API.

# Logic
The `settings.py` file loads this JSON and transforms it into a Python dictionary mapping `key` to `prompt`. The `VllmWorker` then uses these prompts as the `system` message in `chat.completions.create` calls.

# Content Highlights
The library currently includes specialized prompts for:
- **Historical Scripts**: `fraktur_german_19c`, `historical_english`.
- **Handwriting**: Modern cursive for English, German, French, Spanish.
- **Modern Printing**: `modern_english_general`.
- **Technical/Professional**: `scientific_mathematical`, `legal_documents`.
- **East Asian Languages**: `asian_languages_cjk` (covering Chinese, Japanese, Korean).

# Goal
The prompt file provides the structure and category list of the prompt library, enabling the regeneration of the JSON schema and the inclusion of high-quality correction instructions for various document types.
