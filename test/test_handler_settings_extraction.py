import unittest
from unittest.mock import MagicMock, patch
import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Mock dependencies before importing handler
with patch.dict(sys.modules, {
    "runpod": MagicMock(),
    "torch": MagicMock(),
    "torch.multiprocessing": MagicMock(),
    "mineru": MagicMock(),
    "mineru.data": MagicMock(),
    "mineru.data.data_reader_writer": MagicMock(),
    "mineru.data.dataset": MagicMock(),
    "mineru.model": MagicMock(),
    "mineru.model.doc_analyze_by_custom_model": MagicMock(),
}):
    from handler import extract_mineru_settings_from_job_input
    from settings import MinerUSettings

class TestMinerUSettingsExtraction(unittest.TestCase):
    def test_extract_valid_overrides(self):
        job_input = {
            "mineru_workers": 4,
            "mineru_ocr_mode": "ocr",
            "mineru_debug": True,
            "output_format": "markdown"
        }
        settings = extract_mineru_settings_from_job_input(job_input)
        self.assertIsInstance(settings, MinerUSettings)
        self.assertEqual(settings.workers, 4)
        self.assertEqual(settings.ocr_mode, "ocr")
        self.assertTrue(settings.debug)
        self.assertEqual(settings.output_format, "markdown")

    def test_extract_empty_input_uses_defaults(self):
        job_input = {}
        settings = extract_mineru_settings_from_job_input(job_input)
        # Defaults from MinerUSettings
        self.assertEqual(settings.ocr_mode, "auto")
        self.assertEqual(settings.output_format, "markdown")
        self.assertEqual(settings.vram_gb_per_worker, 5)

    def test_extract_unknown_keys_warns_but_ignores(self):
        job_input = {
            "mineru_unknown_field": "value",
            "some_other_key": "ignore"
        }
        with patch("handler.logger.warning") as mock_warn:
            settings = extract_mineru_settings_from_job_input(job_input)
            mock_warn.assert_called_once()
            self.assertIn("Unknown mineru setting 'mineru_unknown_field'", mock_warn.call_args[0][0])

        # Verify it's not on the object
        self.assertFalse(hasattr(settings, "unknown_field"))

    def test_extract_mixed_input(self):
        job_input = {
            "mineru_workers": 2,
            "vllm_model_path": "/some/path", # Should be ignored by MinerU extractor
            "other": "value"
        }
        settings = extract_mineru_settings_from_job_input(job_input)
        self.assertEqual(settings.workers, 2)

if __name__ == "__main__":
    unittest.main()
