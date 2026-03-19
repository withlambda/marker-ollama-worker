# Context
This file, `test/test_handler_image_description_helpers.py`, contains unit tests for the image discovery and description insertion logic in `handler.py`. It uses a comprehensive mocking strategy to test these helper functions without requiring heavy dependencies like `torch` or `marker`.

# Interface

## Mocking Strategy
- `_install_dependency_stubs()`: Programmatically creates and injects lightweight `types.ModuleType` objects into `sys.modules` for `runpod`, `torch`, `marker`, and `vllm_worker`. This prevents `ImportError` and VRAM allocation during tests.
- `DummyPdfConverter`, `DummyConfigParser`: Minimal class stubs to satisfy handler imports.

## Main Test Classes

### `TestHandlerImageDescriptionHelpers`
Verifies the regex-based insertion and file system scanning logic.
- **Tests**:
  - `test_list_extracted_images_for_output_file_filters_and_sorts`: Ensures that only supported image extensions are identified in the output directory and that they are sorted alphabetically.
  - `test_insert_image_descriptions_to_text_file_inserts_in_place`: Verifies that the regex correctly identifies `![alt](path)` tags in Markdown and inserts the description in a blockquote immediately after the tag.
  - `test_insert_image_descriptions_to_text_file_fallback_to_append`: Checks that if an image tag is not found in the text, the description is appended to a new "## Extracted Image Descriptions" section at the end of the file.
  - `test_insert_image_descriptions_to_text_file_skips_non_text_output`: Ensures that JSON output files are not modified by the description logic.

# Logic
The tests use `tempfile.TemporaryDirectory` to simulate an output directory with mixed file types (`.md`, `.png`, `.jpg`, `.txt`). It verifies the string manipulation logic (regex search and replace) that merges vision model outputs back into the primary document.

# Goal
The prompt file provides the mocking strategy and test cases required to recreate the image description helper verification suite, ensuring the robust merging of multi-modal outputs.
