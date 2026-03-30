"""
Unit tests for helper functions that merge vLLM-generated image descriptions
into MinerU text outputs.
"""

import sys
import unittest
import tempfile
import types
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from handler import list_extracted_images_for_output_file, insert_image_descriptions_to_text_file


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

            images = list_extracted_images_for_output_file(
                self.app_config,
                output_file
            )

            self.assertEqual(
                [image.name for image in images],
                ["a-first.JPG", "middle.webp", "z-last.png"],
            )

    def test_list_extracted_images_for_output_file_nested_images(self) -> None:
        """Should find images in 'images/' subfolder relative to output file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            output_file = output_dir / "document.md"
            output_file.write_text("base text", encoding="utf-8")

            # Images in root
            (output_dir / "root.png").write_bytes(b"img")

            # Images in subfolder
            images_dir = output_dir / "images"
            images_dir.mkdir()
            (images_dir / "nested.jpg").write_bytes(b"img")

            images = list_extracted_images_for_output_file(
                self.app_config,
                output_file
            )

            self.assertEqual(
                [image.name for image in images],
                ["nested.jpg", "root.png"],
            )

    def test_insert_image_descriptions_to_text_file_inserts_in_place(self) -> None:
        """Should insert a formatted image-description immediately after its tag in markdown."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "doc.md"
            output_file.write_text(
                "First paragraph.\n\n![img](image_1.png)\n\nSecond paragraph.\n\n![table](image_2.png)\n",
                encoding="utf-8"
            )

            inserted = insert_image_descriptions_to_text_file(
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
            output_file.write_text("Original MinerU text without tags.", encoding="utf-8")

            inserted = insert_image_descriptions_to_text_file(
                app_config=self.app_config,
                output_file_path=output_file,
                image_descriptions=[
                    (Path("missing.png"), "A description of a missing image."),
                ],
            )

            updated_text = output_file.read_text(encoding="utf-8")

            self.assertTrue(inserted)
            self.assertIn("Original MinerU text without tags.", updated_text)
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

            inserted = insert_image_descriptions_to_text_file(
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

            inserted = insert_image_descriptions_to_text_file(
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

            inserted = insert_image_descriptions_to_text_file(
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
