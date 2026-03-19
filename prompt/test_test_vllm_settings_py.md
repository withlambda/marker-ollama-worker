# Context
This file, `test/test_vllm_settings.py`, contains unit tests for the `VllmSettings` class in `settings.py`. It uses the `unittest` framework to verify validation rules, default values, VRAM-based auto-calculations, and environment variable synchronization.

# Interface

## Main Test Classes

### `TestVllmSettingsDefaults`
Verifies that optional fields (e.g., `vllm_host`, `vllm_port`, `vllm_gpu_util`, `vllm_chunk_size`) are assigned their correct default values when not explicitly provided.

### `TestVllmSettingsGpuUtilValidation`
Tests the range validator for `vllm_gpu_util`. It ensures values in (0.0, 1.0] are accepted, while 0.0, negative values, and values > 1.0 are rejected with a `ValidationError`.

### `TestVllmSettingsPortValidation`
Tests the range validator for `vllm_port`. It ensures values in [1, 65535] are accepted, while 0, negative values, and values > 65535 are rejected.

### `TestVllmSettingsMaxNumSeqsAutoCalc`
Verifies the logic that computes `vllm_max_num_seqs` based on `VRAM_GB_TOTAL`, `VRAM_GB_RESERVE`, and `VLLM_VRAM_GB_MODEL`. It checks:
- Correct calculation when VRAM is plentiful.
- Fallback to 1 when VRAM is insufficient.
- Overrides from explicit constructor arguments or environment variables.

### `TestVllmSettingsModelNameDerivation`
Verifies that `vllm_model` is automatically set to the last component of the `vllm_model_path` directory if not provided.

### `TestVllmSettingsPromptResolution`
Tests how `vllm_block_correction_prompt` is resolved by looking up a key in the `GlobalConfig.block_correction_prompts_library`.

### `TestVllmSettingsEnvVarExport`
Ensures that after validation, settings are exported back to `os.environ` so that subprocesses (like the vLLM server) can access them.

### `TestVllmSettingsRequiredFields`
Confirms that missing `vllm_model_path` or `vllm_vram_gb_model` correctly raises a `ValidationError`.

# Logic
The tests use `tempfile.mkdtemp` to simulate a realistic model directory structure and `unittest.TestCase.setUp/tearDown` to ensure environment variable isolation between tests.

# Goal
The prompt file provides the full test suite specification, enabling the exact regeneration of the validation and logic tests for the vLLM configuration system.
