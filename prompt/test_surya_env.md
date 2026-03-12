# `test/surya.env`

## Context
This file defines environment variables specific to the `Surya` library, used for layout analysis and OCR within Marker.

## Variables
*   `MODEL_CACHE_DIR`: `/v/huggingface-cache/hub` (Path to cached Hugging Face models)
*   `DETECTOR_MODEL_CHECKPOINT`: `karlo0/surya_line_det_2.20`
*   `LAYOUT_MODEL_CHECKPOINT`: `karlo0/surya_layout_multimodal`
*   `FOUNDATION_MODEL_CHECKPOINT`: `karlo0/surya_text_recognition`
*   `RECOGNITION_MODEL_CHECKPOINT`: `karlo0/surya_text_recognition`
*   `TABLE_REC_MODEL_CHECKPOINT`: `karlo0/surya_tablerec`
*   `OCR_ERROR_MODEL_CHECKPOINT`: `karlo0/tarun-menta_ocr_error_detection`
