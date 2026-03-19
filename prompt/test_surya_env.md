# Context
This file, `test/surya.env`, defines environment variables for the `surya` library, which is a dependency of `marker-pdf` used for layout analysis and OCR. It specifies the local paths and model checkpoints.

# Interface

## Variables
- `MODEL_CACHE_DIR`: Set to `/v/huggingface-cache/hub`.
- `*_MODEL_CHECKPOINT`: Specifies the Hugging Face IDs for the detector, layout, and recognition models.

# Logic
The file is a standard shell-compatible environment file. It is used by `docker run` via the `--env-file` flag in `test/run.sh`.

# Goal
The prompt file captures the specific model checkpoints and cache configuration required by the `surya` library for testing.
