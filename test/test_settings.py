import os
import unittest

from pydantic import ValidationError

from settings import MinerUSettings


class TestMinerUSettings(unittest.TestCase):
    def setUp(self):
        # Set required env vars for GlobalConfig which might be instantiated
        os.environ["VOLUME_ROOT_MOUNT_PATH"] = "/tmp"
        os.environ["VRAM_GB_TOTAL"] = "24"

    def test_mineru_settings_defaults(self):
        settings = MinerUSettings()
        self.assertEqual(settings.ocr_mode, "auto")
        self.assertEqual(settings.output_format, "markdown")
        self.assertEqual(settings.vram_gb_per_worker, 5)
        self.assertFalse(settings.disable_image_extraction)
        self.assertFalse(settings.debug)
        self.assertFalse(settings.disable_maxtasksperchild)
        self.assertEqual(settings.maxtasksperchild, 25)

    def test_mineru_settings_maxtasksperchild_disabled(self):
        settings = MinerUSettings(disable_maxtasksperchild=True)
        self.assertTrue(settings.disable_maxtasksperchild)
        self.assertIsNone(settings.maxtasksperchild)

    def test_mineru_settings_env_vars(self):
        os.environ["MINERU_WORKERS"] = "4"
        os.environ["MINERU_OCR_MODE"] = "ocr"
        os.environ["MINERU_DEBUG"] = "True"

        settings = MinerUSettings()
        self.assertEqual(settings.workers, 4)
        self.assertEqual(settings.ocr_mode, "ocr")
        self.assertTrue(settings.debug)

        # Cleanup
        del os.environ["MINERU_WORKERS"]
        del os.environ["MINERU_OCR_MODE"]
        del os.environ["MINERU_DEBUG"]

    def test_mineru_settings_invalid_output_format(self):
        with self.assertRaises(ValidationError):
            MinerUSettings(output_format="json")

    def test_mineru_settings_extra_fields_ignored(self):
        # extra='ignore' should allow unknown fields without error
        settings = MinerUSettings(unknown_field="value")
        self.assertFalse(hasattr(settings, "unknown_field"))

    def test_mineru_settings_removed_fields_not_accepted(self):
        # Since extra='ignore', they are just ignored, not raising error
        # But we can verify they are not in the model
        settings = MinerUSettings(paginate_output=True, processors="test")
        self.assertFalse(hasattr(settings, "paginate_output"))
        self.assertFalse(hasattr(settings, "processors"))

if __name__ == "__main__":
    unittest.main()
