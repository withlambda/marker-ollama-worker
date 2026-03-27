"""
Unit tests for helper functions that merge vLLM-generated image descriptions
into marker text outputs.
"""

import importlib
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock
from importlib.machinery import ModuleSpec
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _install_dependency_stubs() -> None:
    """Installs lightweight stubs for optional heavy dependencies."""
    def _make_module(name: str) -> types.ModuleType:
        module = types.ModuleType(name)
        module.__spec__ = ModuleSpec(name, loader=None)
        return module

    runpod_module = _make_module("runpod")
    runpod_module.serverless = types.SimpleNamespace(start=lambda *_args, **_kwargs: None)
    sys.modules.setdefault("runpod", runpod_module)

    # openai and vllm are needed for vllm_worker import to succeed
    openai_module = _make_module("openai")
    openai_module.__path__ = []
    openai_module.AsyncOpenAI = MagicMock()
    sys.modules.setdefault("openai", openai_module)

    openai_types_module = _make_module("openai.types")
    openai_types_module.__path__ = []
    sys.modules.setdefault("openai.types", openai_types_module)
    openai_module.types = openai_types_module

    openai_types_chat_module = _make_module("openai.types.chat")
    openai_types_chat_module.__path__ = []
    openai_types_chat_module.ChatCompletionUserMessageParam = dict
    openai_types_chat_module.ChatCompletionSystemMessageParam = dict
    openai_types_chat_module.ChatCompletionContentPartImageParam = dict
    openai_types_chat_module.ChatCompletionContentPartTextParam = dict
    sys.modules.setdefault("openai.types.chat", openai_types_chat_module)
    openai_types_module.chat = openai_types_chat_module

    # Some versions of openai import specific params from submodules
    openai_image_part_module = _make_module("openai.types.chat.chat_completion_content_part_image_param")
    openai_image_part_module.ImageURL = dict
    sys.modules.setdefault("openai.types.chat.chat_completion_content_part_image_param", openai_image_part_module)

    openai_text_part_module = _make_module("openai.types.chat.chat_completion_content_part_text_param")
    sys.modules.setdefault("openai.types.chat.chat_completion_content_part_text_param", openai_text_part_module)

    vllm_module = _make_module("vllm")
    sys.modules.setdefault("vllm", vllm_module)

    torch_module = _make_module("torch")
    torch_module.__path__ = []
    torch_module.cuda = types.SimpleNamespace(
        empty_cache=lambda: None,
        is_available=lambda: False,
        get_device_name=lambda *_args, **_kwargs: "stub-device",
        get_device_properties=lambda *_args, **_kwargs: types.SimpleNamespace(total_memory=0),
        mem_get_info=lambda *_args, **_kwargs: (0, 0),
    )
    sys.modules.setdefault("torch", torch_module)

    torch_mp_module = _make_module("torch.multiprocessing")
    torch_mp_module.set_start_method = lambda *_args, **_kwargs: None
    sys.modules.setdefault("torch.multiprocessing", torch_mp_module)

    marker_module = _make_module("marker")
    sys.modules.setdefault("marker", marker_module)
    sys.modules.setdefault("marker.converters", _make_module("marker.converters"))

    marker_converters_pdf_module = _make_module("marker.converters.pdf")

    class DummyPdfConverter:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def __call__(self, *_args, **_kwargs):
            return None

    marker_converters_pdf_module.PdfConverter = DummyPdfConverter
    sys.modules.setdefault("marker.converters.pdf", marker_converters_pdf_module)

    marker_models_module = _make_module("marker.models")
    marker_models_module.create_model_dict = lambda: {}
    sys.modules.setdefault("marker.models", marker_models_module)

    marker_parser_module = _make_module("marker.config.parser")

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
    sys.modules.setdefault("marker.config", _make_module("marker.config"))
    sys.modules.setdefault("marker.config.parser", marker_parser_module)

    marker_output_module = _make_module("marker.output")
    marker_output_module.text_from_rendered = lambda *_args, **_kwargs: ("", {}, [])
    sys.modules.setdefault("marker.output", marker_output_module)


def _import_handler_module():
    """Imports handler module with dependency stubs when needed."""
    try:
        return importlib.import_module("handler")
    except (ModuleNotFoundError, ImportError, ValueError):
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

    def test_insert_image_descriptions_to_text_file_localized(self) -> None:
        """Should use localized wrappers when provided as overrides."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "doc.md"
            output_file.write_text(
                "First paragraph.\n\n![img](image_1.png)\n",
                encoding="utf-8"
            )

            # German overrides
            heading_override = "**[BEGINN BILDBESCHREIBUNG]**"
            end_override = "**[ENDE BILDBESCHREIBUNG]**"
            section_heading_override = "## Extrahierte Bildbeschreibungen"

            inserted = handler_module.insert_image_descriptions_to_text_file(
                app_config=self.app_config,
                output_file_path=output_file,
                image_descriptions=[
                    (Path("image_1.png"), "Eine Beschreibung auf Deutsch."),
                ],
                heading_override=heading_override,
                end_override=end_override,
                section_heading_override=section_heading_override
            )

            updated_text = output_file.read_text(encoding="utf-8")

            self.assertTrue(inserted)
            self.assertIn(heading_override, updated_text)
            self.assertIn(end_override, updated_text)
            self.assertIn("Eine Beschreibung auf Deutsch.", updated_text)

    def test_insert_image_descriptions_to_text_file_fallback_localized(self) -> None:
        """Should use localized fallback section heading when provided."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "doc.md"
            output_file.write_text("Text without tags.", encoding="utf-8")

            section_heading_override = "## Extrahierte Bildbeschreibungen"

            inserted = handler_module.insert_image_descriptions_to_text_file(
                app_config=self.app_config,
                output_file_path=output_file,
                image_descriptions=[
                    (Path("missing.png"), "Beschreibung."),
                ],
                section_heading_override=section_heading_override
            )

            updated_text = output_file.read_text(encoding="utf-8")

            self.assertTrue(inserted)
            self.assertIn(section_heading_override, updated_text)


if __name__ == "__main__":
    unittest.main()
