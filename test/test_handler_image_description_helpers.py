"""
Unit tests for helper functions that merge vLLM-generated image descriptions
into marker text outputs.
"""

import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _install_dependency_stubs() -> None:
    """Installs lightweight stubs for optional heavy dependencies."""
    runpod_module = types.ModuleType("runpod")
    runpod_module.serverless = types.SimpleNamespace(start=lambda *_args, **_kwargs: None)
    sys.modules.setdefault("runpod", runpod_module)

    torch_module = types.ModuleType("torch")
    torch_module.cuda = types.SimpleNamespace(
        empty_cache=lambda: None,
        is_available=lambda: False,
        get_device_name=lambda *_args, **_kwargs: "stub-device",
        get_device_properties=lambda *_args, **_kwargs: types.SimpleNamespace(total_memory=0),
        mem_get_info=lambda *_args, **_kwargs: (0, 0),
    )
    sys.modules.setdefault("torch", torch_module)

    marker_module = types.ModuleType("marker")
    sys.modules.setdefault("marker", marker_module)
    sys.modules.setdefault("marker.converters", types.ModuleType("marker.converters"))

    marker_converters_pdf_module = types.ModuleType("marker.converters.pdf")

    class DummyPdfConverter:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def __call__(self, *_args, **_kwargs):
            return None

    marker_converters_pdf_module.PdfConverter = DummyPdfConverter
    sys.modules.setdefault("marker.converters.pdf", marker_converters_pdf_module)

    marker_models_module = types.ModuleType("marker.models")
    marker_models_module.create_model_dict = lambda: {}
    sys.modules.setdefault("marker.models", marker_models_module)

    marker_parser_module = types.ModuleType("marker.config.parser")

    class DummyConfigParser:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def generate_config_dict(self):
            return {}

        def get_processors(self):
            return []

        def get_renderer(self):
            return None

    marker_parser_module.ConfigParser = DummyConfigParser
    sys.modules.setdefault("marker.config", types.ModuleType("marker.config"))
    sys.modules.setdefault("marker.config.parser", marker_parser_module)

    marker_output_module = types.ModuleType("marker.output")
    marker_output_module.text_from_rendered = lambda *_args, **_kwargs: ("", {}, [])
    sys.modules.setdefault("marker.output", marker_output_module)

    vllm_worker_module = types.ModuleType("vllm_worker")

    class DummyVllmWorker:
        pass

    vllm_worker_module.VllmWorker = DummyVllmWorker
    sys.modules.setdefault("vllm_worker", vllm_worker_module)


def _import_handler_module():
    """Imports handler module with dependency stubs when needed."""
    try:
        return importlib.import_module("handler")
    except ModuleNotFoundError:
        _install_dependency_stubs()
        sys.modules.pop("handler", None)
        return importlib.import_module("handler")


handler_module = _import_handler_module()


class TestHandlerImageDescriptionHelpers(unittest.TestCase):
    """Tests for image discovery and text-append helper functions."""

    def setUp(self) -> None:
        """Set up test configuration that mimics GlobalConfig."""
        self.app_config = types.SimpleNamespace(
            IMAGE_FILE_EXTENSIONS={".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"},
            FILE_ENCODING="utf-8",
            image_description_section_heading="## Extracted Image Descriptions",
            image_description_heading="**[BEGIN IMAGE DESCRIPTION]**",
            image_description_end="**[END IMAGE DESCRIPTION]**"
        )

    def test_list_extracted_images_for_output_file_filters_and_sorts(self) -> None:
        """Should return only image files sorted by filename in the output folder."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            output_file = output_dir / "document.md"
            output_file.write_text("base text", encoding="utf-8")

            (output_dir / "z-last.png").write_bytes(b"img")
            (output_dir / "a-first.JPG").write_bytes(b"img")
            (output_dir / "middle.webp").write_bytes(b"img")
            (output_dir / "notes.txt").write_text("ignore", encoding="utf-8")

            images = handler_module.list_extracted_images_for_output_file(
                self.app_config,
                output_file
            )

            self.assertEqual(
                [image.name for image in images],
                ["a-first.JPG", "middle.webp", "z-last.png"],
            )

    def test_insert_image_descriptions_to_text_file_inserts_in_place(self) -> None:
        """Should insert a formatted image-description immediately after its tag in markdown."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "doc.md"
            output_file.write_text(
                "First paragraph.\n\n![img](image_1.png)\n\nSecond paragraph.\n\n![table](image_2.png)\n",
                encoding="utf-8"
            )

            inserted = handler_module.insert_image_descriptions_to_text_file(
                app_config=self.app_config,
                output_file_path=output_file,
                image_descriptions=[
                    (Path("image_1.png"), "A flowchart with three connected boxes."),
                    (Path("image_2.png"), "A table with four rows and two columns."),
                ],
            )

            updated_text = output_file.read_text(encoding="utf-8")

            self.assertTrue(inserted)
            # Check for in-place insertion
            self.assertIn("![img](image_1.png)\n\n> **[BEGIN IMAGE DESCRIPTION]**\n> A flowchart with three connected boxes.\n> **[END IMAGE DESCRIPTION]**", updated_text)
            self.assertIn("![table](image_2.png)\n\n> **[BEGIN IMAGE DESCRIPTION]**\n> A table with four rows and two columns.\n> **[END IMAGE DESCRIPTION]**", updated_text)
            # Should not contain the fallback section if all were placed
            self.assertNotIn("## Extracted Image Descriptions", updated_text)

    def test_insert_image_descriptions_to_text_file_fallback_to_append(self) -> None:
        """Should append descriptions to the end if the image tags are not found in the text."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "doc.md"
            output_file.write_text("Original marker text without tags.", encoding="utf-8")

            inserted = handler_module.insert_image_descriptions_to_text_file(
                app_config=self.app_config,
                output_file_path=output_file,
                image_descriptions=[
                    (Path("missing.png"), "A description of a missing image."),
                ],
            )

            updated_text = output_file.read_text(encoding="utf-8")

            self.assertTrue(inserted)
            self.assertIn("Original marker text without tags.", updated_text)
            self.assertIn("## Extracted Image Descriptions", updated_text)
            self.assertIn("### Image: `missing.png`", updated_text)
            # Updated to match blockquote format
            self.assertIn("> **[BEGIN IMAGE DESCRIPTION]**", updated_text)
            self.assertIn("> A description of a missing image.", updated_text)
            self.assertIn("> **[END IMAGE DESCRIPTION]**", updated_text)

    def test_insert_image_descriptions_to_text_file_skips_non_text_output(self) -> None:
        """Should not modify non-text outputs such as JSON files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "doc.json"
            original_json = '{"content": "value"}'
            output_file.write_text(original_json, encoding="utf-8")

            inserted = handler_module.insert_image_descriptions_to_text_file(
                app_config=self.app_config,
                output_file_path=output_file,
                image_descriptions=[(Path("image_1.png"), "Some description")],
            )

            self.assertFalse(inserted)
            self.assertEqual(output_file.read_text(encoding="utf-8"), original_json)


if __name__ == "__main__":
    unittest.main()
