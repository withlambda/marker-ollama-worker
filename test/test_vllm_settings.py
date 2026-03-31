"""
Unit tests for VllmSettings validation logic, defaults, computed fields, and error handling.

Tests cover:
- Default values for all optional fields.
- Required field validation (vllm_model_path, vllm_vram_gb_model).
- Field validators: vllm_gpu_util range (0.0–1.0), vllm_port range (1–65535).
- VRAM-based auto-calculation of vllm_max_num_seqs.
- Model name derivation from vllm_model_path.
- Block correction prompt resolution from library and custom override.
- Environment variable export logic.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure the project root is on sys.path so settings can be imported
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pydantic import ValidationError
from settings import GlobalConfig, VllmSettings


def _make_global_config(tmp_dir: str, **overrides) -> GlobalConfig:
    """Create a minimal GlobalConfig for testing, using the given tmp_dir as volume root."""
    defaults = {
        "VOLUME_ROOT_MOUNT_PATH": tmp_dir,
        "VRAM_GB_TOTAL": "24",
    }
    defaults.update(overrides)
    return GlobalConfig(**defaults)


def _make_vllm_settings(
    app_config: GlobalConfig,
    model_path: str,
    vram_gb_model: int = 6,
    **kwargs
) -> VllmSettings:
    """Create a VllmSettings instance with required fields pre-filled."""
    return VllmSettings(
        app_config=app_config,
        NOTELM_VLLM_MODEL_PATH=model_path,
        NOTELM_VLLM_VRAM_GB_MODEL=vram_gb_model,
        **kwargs,
    )


class TestVllmSettingsDefaults(unittest.TestCase):
    """Verify that default values are applied correctly for optional fields."""

    def setUp(self):
        """Set up a temporary directory structure for model path validation."""
        self.tmp_dir = tempfile.mkdtemp()
        self.model_dir = os.path.join(self.tmp_dir, "my-model")
        os.makedirs(self.model_dir, exist_ok=True)
        # Clear any VLLM env vars that could interfere
        self._clear_vllm_env_vars()

    def tearDown(self):
        """Clean up temporary directories and env vars."""
        self._clear_vllm_env_vars()
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @staticmethod
    def _clear_vllm_env_vars():
        """Remove all VLLM_* environment variables to prevent test interference."""
        for key in list(os.environ.keys()):
            if key.startswith("NOTELM_VLLM_"):
                del os.environ[key]

    def test_default_host(self):
        """Verify default vllm_host value."""
        cfg = _make_global_config(self.tmp_dir)
        settings = _make_vllm_settings(cfg, self.model_dir)
        self.assertEqual(settings.vllm_host, "127.0.0.1")

    def test_default_port(self):
        """Verify default vllm_port value."""
        cfg = _make_global_config(self.tmp_dir)
        settings = _make_vllm_settings(cfg, self.model_dir)
        self.assertEqual(settings.vllm_port, 8001)

    def test_default_gpu_util(self):
        """Verify default vllm_gpu_util value."""
        cfg = _make_global_config(self.tmp_dir)
        settings = _make_vllm_settings(cfg, self.model_dir)
        self.assertAlmostEqual(settings.vllm_gpu_util, 0.85)

    def test_default_max_model_len(self):
        """Verify default vllm_max_model_len value."""
        cfg = _make_global_config(self.tmp_dir)
        settings = _make_vllm_settings(cfg, self.model_dir)
        self.assertEqual(settings.vllm_max_model_len, 16384)

    def test_default_startup_timeout(self):
        """Verify default vllm_startup_timeout value."""
        cfg = _make_global_config(self.tmp_dir)
        settings = _make_vllm_settings(cfg, self.model_dir)
        self.assertEqual(settings.vllm_startup_timeout, 120)

    def test_default_vram_recovery_delay(self):
        """Verify default vllm_vram_recovery_delay value."""
        cfg = _make_global_config(self.tmp_dir)
        settings = _make_vllm_settings(cfg, self.model_dir)
        self.assertEqual(settings.vllm_vram_recovery_delay, 10)

    def test_default_max_retries(self):
        """Verify default vllm_max_retries value."""
        cfg = _make_global_config(self.tmp_dir)
        settings = _make_vllm_settings(cfg, self.model_dir)
        self.assertEqual(settings.vllm_max_retries, 3)

    def test_default_retry_delay(self):
        """Verify default vllm_retry_delay value."""
        cfg = _make_global_config(self.tmp_dir)
        settings = _make_vllm_settings(cfg, self.model_dir)
        self.assertAlmostEqual(settings.vllm_retry_delay, 2.0)

    def test_default_chunk_size(self):
        """Verify default vllm_chunk_size value."""
        cfg = _make_global_config(self.tmp_dir)
        settings = _make_vllm_settings(cfg, self.model_dir)
        self.assertEqual(settings.vllm_chunk_size, settings.vllm_max_model_len // 2)

    def test_default_chunk_workers(self):
        """Verify default vllm_chunk_workers value."""
        cfg = _make_global_config(self.tmp_dir)
        settings = _make_vllm_settings(cfg, self.model_dir)
        self.assertEqual(settings.vllm_chunk_workers, 16)

    def test_default_token_safety_margin(self):
        """Verify default vllm_chat_completion_token_safety_margin value."""
        cfg = _make_global_config(self.tmp_dir)
        settings = _make_vllm_settings(cfg, self.model_dir)
        self.assertEqual(settings.vllm_chat_completion_token_safety_margin, 50)

    def test_default_tiktoken_encoding_name(self):
        """Verify default vllm_tiktoken_encoding_name value."""
        cfg = _make_global_config(self.tmp_dir)
        settings = _make_vllm_settings(cfg, self.model_dir)
        self.assertEqual(settings.vllm_tiktoken_encoding_name, "gpt2")

    def test_optional_fields_are_none_by_default(self):
        """Verify optional prompt fields default to None."""
        cfg = _make_global_config(self.tmp_dir)
        settings = _make_vllm_settings(cfg, self.model_dir)
        self.assertIsNone(settings.vllm_block_correction_prompt_key)
        self.assertIsNone(settings.vllm_block_correction_prompt)
        self.assertIsNone(settings.vllm_image_description_prompt)


class TestVllmSettingsGpuUtilValidation(unittest.TestCase):
    """Test vllm_gpu_util field validator (must be between 0.0 exclusive and 1.0 inclusive)."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.model_dir = os.path.join(self.tmp_dir, "test-model")
        os.makedirs(self.model_dir, exist_ok=True)
        self._clear_vllm_env_vars()

    def tearDown(self):
        self._clear_vllm_env_vars()
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @staticmethod
    def _clear_vllm_env_vars():
        for key in list(os.environ.keys()):
            if key.startswith("NOTELM_VLLM_"):
                del os.environ[key]

    def test_gpu_util_valid_mid_range(self):
        """Accept a valid mid-range gpu_util value."""
        cfg = _make_global_config(self.tmp_dir)
        settings = _make_vllm_settings(cfg, self.model_dir, NOTELM_VLLM_GPU_UTIL=0.5)
        self.assertAlmostEqual(settings.vllm_gpu_util, 0.5)

    def test_gpu_util_valid_max(self):
        """Accept gpu_util = 1.0 (upper boundary, inclusive)."""
        cfg = _make_global_config(self.tmp_dir)
        settings = _make_vllm_settings(cfg, self.model_dir, NOTELM_VLLM_GPU_UTIL=1.0)
        self.assertAlmostEqual(settings.vllm_gpu_util, 1.0)

    def test_gpu_util_zero_rejected(self):
        """Reject gpu_util = 0.0 (lower boundary, exclusive)."""
        cfg = _make_global_config(self.tmp_dir)
        with self.assertRaises(ValidationError) as ctx:
            _make_vllm_settings(cfg, self.model_dir, NOTELM_VLLM_GPU_UTIL=0.0)
        self.assertIn("vllm_gpu_util", str(ctx.exception))

    def test_gpu_util_negative_rejected(self):
        """Reject negative gpu_util values."""
        cfg = _make_global_config(self.tmp_dir)
        with self.assertRaises(ValidationError):
            _make_vllm_settings(cfg, self.model_dir, NOTELM_VLLM_GPU_UTIL=-0.5)

    def test_gpu_util_above_one_rejected(self):
        """Reject gpu_util > 1.0."""
        cfg = _make_global_config(self.tmp_dir)
        with self.assertRaises(ValidationError):
            _make_vllm_settings(cfg, self.model_dir, NOTELM_VLLM_GPU_UTIL=1.5)


class TestVllmSettingsPortValidation(unittest.TestCase):
    """Test vllm_port field validator (must be between 1 and 65535)."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.model_dir = os.path.join(self.tmp_dir, "test-model")
        os.makedirs(self.model_dir, exist_ok=True)
        self._clear_vllm_env_vars()

    def tearDown(self):
        self._clear_vllm_env_vars()
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @staticmethod
    def _clear_vllm_env_vars():
        for key in list(os.environ.keys()):
            if key.startswith("NOTELM_VLLM_"):
                del os.environ[key]

    def test_port_valid_default(self):
        """Default port 8001 is valid."""
        cfg = _make_global_config(self.tmp_dir)
        settings = _make_vllm_settings(cfg, self.model_dir)
        self.assertEqual(settings.vllm_port, 8001)

    def test_port_valid_min(self):
        """Accept port = 1 (lower boundary)."""
        cfg = _make_global_config(self.tmp_dir)
        settings = _make_vllm_settings(cfg, self.model_dir, NOTELM_VLLM_PORT=1)
        self.assertEqual(settings.vllm_port, 1)

    def test_port_valid_max(self):
        """Accept port = 65535 (upper boundary)."""
        cfg = _make_global_config(self.tmp_dir)
        settings = _make_vllm_settings(cfg, self.model_dir, NOTELM_VLLM_PORT=65535)
        self.assertEqual(settings.vllm_port, 65535)

    def test_port_zero_rejected(self):
        """Reject port = 0."""
        cfg = _make_global_config(self.tmp_dir)
        with self.assertRaises(ValidationError) as ctx:
            _make_vllm_settings(cfg, self.model_dir, NOTELM_VLLM_PORT=0)
        self.assertIn("vllm_port", str(ctx.exception))

    def test_port_above_max_rejected(self):
        """Reject port > 65535."""
        cfg = _make_global_config(self.tmp_dir)
        with self.assertRaises(ValidationError):
            _make_vllm_settings(cfg, self.model_dir, NOTELM_VLLM_PORT=70000)

    def test_port_negative_rejected(self):
        """Reject negative port values."""
        cfg = _make_global_config(self.tmp_dir)
        with self.assertRaises(ValidationError):
            _make_vllm_settings(cfg, self.model_dir, NOTELM_VLLM_PORT=-1)


class TestVllmSettingsMaxNumSeqsAutoCalc(unittest.TestCase):
    """Test VRAM-based auto-calculation of vllm_max_num_seqs."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.model_dir = os.path.join(self.tmp_dir, "test-model")
        os.makedirs(self.model_dir, exist_ok=True)
        self._clear_vllm_env_vars()

    def tearDown(self):
        self._clear_vllm_env_vars()
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @staticmethod
    def _clear_vllm_env_vars():
        for key in list(os.environ.keys()):
            if key.startswith("NOTELM_VLLM_"):
                del os.environ[key]

    def test_auto_calc_with_sufficient_vram(self):
        """Auto-calc yields >1 seq when plenty of VRAM is available."""
        # vram_total=24, reserve=4, model=6 => available=14
        # context_vram = 0.00013 * 16384 ≈ 2.13 => seqs = int(14 / 2.13) = 6
        cfg = _make_global_config(self.tmp_dir, VRAM_GB_TOTAL="24", VRAM_GB_RESERVE="4")
        settings = _make_vllm_settings(cfg, self.model_dir, vram_gb_model=6)
        expected = max(1, int((24 - 4 - 6) // (0.00013 * 16384)))
        self.assertEqual(settings.vllm_max_num_seqs, expected)
        self.assertGreater(settings.vllm_max_num_seqs, 1)

    def test_auto_calc_falls_to_one_when_no_vram(self):
        """Auto-calc yields 1 when available VRAM is zero or negative."""
        # vram_total=8, reserve=4, model=6 => available=-2 => 1
        cfg = _make_global_config(self.tmp_dir, VRAM_GB_TOTAL="8", VRAM_GB_RESERVE="4")
        settings = _make_vllm_settings(cfg, self.model_dir, vram_gb_model=6)
        self.assertEqual(settings.vllm_max_num_seqs, 1)

    def test_explicit_max_num_seqs_overrides_auto_calc(self):
        """Explicitly providing vllm_max_num_seqs skips auto-calculation."""
        cfg = _make_global_config(self.tmp_dir)
        settings = _make_vllm_settings(
            cfg, self.model_dir, vllm_max_num_seqs=42
        )
        self.assertEqual(settings.vllm_max_num_seqs, 42)

    def test_env_var_max_num_seqs_overrides_auto_calc(self):
        """Setting NOTELM_VLLM_MAX_NUM_SEQS env var skips auto-calculation."""
        os.environ["NOTELM_VLLM_MAX_NUM_SEQS"] = "99"
        cfg = _make_global_config(self.tmp_dir)
        settings = _make_vllm_settings(cfg, self.model_dir)
        self.assertEqual(settings.vllm_max_num_seqs, 99)


class TestVllmSettingsModelNameDerivation(unittest.TestCase):
    """Test that vllm_model is correctly derived from vllm_model_path."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self._clear_vllm_env_vars()

    def tearDown(self):
        self._clear_vllm_env_vars()
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @staticmethod
    def _clear_vllm_env_vars():
        for key in list(os.environ.keys()):
            if key.startswith("NOTELM_VLLM_"):
                del os.environ[key]

    def test_model_name_derived_from_path(self):
        """Model name is derived from the last component of vllm_model_path."""
        model_dir = os.path.join(self.tmp_dir, "Qwen3-VL-8B")
        os.makedirs(model_dir, exist_ok=True)
        cfg = _make_global_config(self.tmp_dir)
        settings = _make_vllm_settings(cfg, model_dir)
        self.assertEqual(settings.vllm_model, "Qwen3-VL-8B")

    def test_explicit_model_name_preserved(self):
        """Explicitly provided vllm_model is not overridden."""
        model_dir = os.path.join(self.tmp_dir, "some-model")
        os.makedirs(model_dir, exist_ok=True)
        cfg = _make_global_config(self.tmp_dir)
        settings = _make_vllm_settings(cfg, model_dir, NOTELM_VLLM_MODEL="custom-name")
        self.assertEqual(settings.vllm_model, "custom-name")


class TestVllmSettingsPromptResolution(unittest.TestCase):
    """Test block correction prompt resolution from library and custom override."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.model_dir = os.path.join(self.tmp_dir, "test-model")
        os.makedirs(self.model_dir, exist_ok=True)
        self._clear_vllm_env_vars()

    def tearDown(self):
        self._clear_vllm_env_vars()
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @staticmethod
    def _clear_vllm_env_vars():
        for key in list(os.environ.keys()):
            if key.startswith("NOTELM_VLLM_"):
                del os.environ[key]

    def test_prompt_resolved_from_library_key(self):
        """Block correction prompt is loaded from the library when a valid key is given."""
        cfg = _make_global_config(self.tmp_dir)
        # Inject a prompt into the library
        object.__setattr__(cfg, 'block_correction_prompts_library', {"default": "Fix OCR errors."})
        settings = _make_vllm_settings(
            cfg, self.model_dir,
            NOTELM_VLLM_BLOCK_CORRECTION_PROMPT_KEY="default"
        )
        self.assertEqual(settings.vllm_block_correction_prompt, "Fix OCR errors.")

    def test_invalid_prompt_key_leaves_prompt_none(self):
        """An invalid prompt key logs a warning and leaves prompt as None."""
        cfg = _make_global_config(self.tmp_dir)
        object.__setattr__(cfg, 'block_correction_prompts_library', {"default": "Fix OCR errors."})
        settings = _make_vllm_settings(
            cfg, self.model_dir,
            NOTELM_VLLM_BLOCK_CORRECTION_PROMPT_KEY="nonexistent"
        )
        self.assertIsNone(settings.vllm_block_correction_prompt)

    def test_custom_prompt_overrides_library(self):
        """A directly provided prompt takes precedence over library lookup."""
        cfg = _make_global_config(self.tmp_dir)
        object.__setattr__(cfg, 'block_correction_prompts_library', {"default": "Library prompt."})
        settings = _make_vllm_settings(
            cfg, self.model_dir,
            NOTELM_VLLM_BLOCK_CORRECTION_PROMPT="Custom prompt override.",
            NOTELM_VLLM_BLOCK_CORRECTION_PROMPT_KEY="default"
        )
        self.assertEqual(settings.vllm_block_correction_prompt, "Custom prompt override.")


class TestVllmSettingsEnvVarExport(unittest.TestCase):
    """Test that VllmSettings does not auto-export unsupported vLLM env vars."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.model_dir = os.path.join(self.tmp_dir, "test-model")
        os.makedirs(self.model_dir, exist_ok=True)
        self._clear_vllm_env_vars()

    def tearDown(self):
        self._clear_vllm_env_vars()
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @staticmethod
    def _clear_vllm_env_vars():
        for key in list(os.environ.keys()):
            if key.startswith("NOTELM_VLLM_"):
                del os.environ[key]

    def test_env_vars_not_exported_when_not_set(self):
        """VllmSettings keeps process env untouched for vLLM/app vLLM settings."""
        cfg = _make_global_config(self.tmp_dir)
        _make_vllm_settings(cfg, self.model_dir)
        self.assertIsNone(os.environ.get("NOTELM_VLLM_HOST"))
        self.assertIsNone(os.environ.get("NOTELM_VLLM_PORT"))
        self.assertIsNone(os.environ.get("NOTELM_VLLM_GPU_UTIL"))
        self.assertIsNone(os.environ.get("NOTELM_VLLM_MAX_MODEL_LEN"))
        self.assertIsNone(os.environ.get("NOTELM_VLLM_MAX_NUM_SEQS"))

    def test_existing_env_vars_are_not_modified(self):
        """Pre-set env variables remain unchanged by VllmSettings construction."""
        os.environ["NOTELM_VLLM_HOST"] = "custom-host"
        cfg = _make_global_config(self.tmp_dir)
        _make_vllm_settings(cfg, self.model_dir)
        self.assertEqual(os.environ.get("NOTELM_VLLM_HOST"), "custom-host")


class TestVllmSettingsRequiredFields(unittest.TestCase):
    """Test that missing required fields raise validation errors."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.model_dir = os.path.join(self.tmp_dir, "test-model")
        os.makedirs(self.model_dir, exist_ok=True)
        self._clear_vllm_env_vars()

    def tearDown(self):
        self._clear_vllm_env_vars()
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @staticmethod
    def _clear_vllm_env_vars():
        for key in list(os.environ.keys()):
            if key.startswith("NOTELM_VLLM_"):
                del os.environ[key]

    def test_missing_vram_gb_model_raises_error(self):
        """VllmSettings requires vllm_vram_gb_model."""
        cfg = _make_global_config(self.tmp_dir)
        with self.assertRaises(ValidationError) as ctx:
            VllmSettings(app_config=cfg, NOTELM_VLLM_MODEL_PATH=self.model_dir)
        self.assertIn("NOTELM_VLLM_VRAM_GB_MODEL", str(ctx.exception))

    def test_invalid_model_path_raises_error(self):
        """VllmSettings rejects a non-existent directory for vllm_model_path."""
        cfg = _make_global_config(self.tmp_dir)
        with self.assertRaises(ValidationError):
            VllmSettings(
                app_config=cfg,
                NOTELM_VLLM_MODEL_PATH="/nonexistent/path/to/model",
                NOTELM_VLLM_VRAM_GB_MODEL=6,
            )


if __name__ == "__main__":
    unittest.main()
