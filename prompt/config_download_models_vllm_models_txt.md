# Context
This file, `config/download-models/vllm-models.txt`, is a text file that contains a list of Hugging Face model IDs required by the `vLLM` server for document post-processing.

# Interface
The file is a simple list with one model ID per line. Empty lines and lines starting with `#` are ignored by the download scripts.

# Logic
The `config/download-models/download-models-from-hf.sh` script reads this file and downloads each listed model into the project's model cache.

# Content Highlights
The current list contains the optimized instruction-tuned model for document-level post-processing:
- `unsloth/SmolLM2-135M-Instruct-GGUF`.

# Goal
The prompt file provides the structure and content of the model list, enabling the exact regeneration of the model requirement specification for the vLLM worker.
