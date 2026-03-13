# `block_correction_prompts.json`

## Context
This JSON file serves as a catalog of prompt templates for the Ollama LLM post-processing phase. It allows users to select different strategies for OCR correction and formatting by specifying a key in their job input.

## Interface
The file is a JSON object where keys are prompt identifiers and values are the corresponding prompt strings.

### Current Prompts

*   `default`: A general-purpose prompt for fixing OCR errors, improving formatting, and ensuring the output is valid Markdown. It instructs the LLM to preserve the original meaning while cleaning up noise.
*   `aggressive`: A more interventionist prompt that may perform more significant restructuring to improve readability.
*   `minimal`: A prompt that focuses strictly on correcting obvious character-level OCR errors without changing the document structure.

## Logic
The `handler.py` script loads this file into `BLOCK_CORRECTION_PROMPT_LIBRARY`. 
When a job is received:
1. If `ollama_block_correction_prompt` is provided in the input, it is used directly.
2. Otherwise, if `block_correction_prompt_key` is provided, it is used to look up a prompt in this library.
3. If neither is provided, it defaults to the `default` key.

## Format Requirements
Values MUST be strings. They should ideally contain instructions for the LLM on how to process the text "chunks" it receives.
