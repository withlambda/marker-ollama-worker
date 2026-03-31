import unittest
from pathlib import Path
import tempfile
import sys
import types

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from handler import insert_image_descriptions_to_text_file, list_extracted_images_for_output_file

class TestMinerURegressions(unittest.TestCase):
    def setUp(self):
        self.app_config = types.SimpleNamespace(
            IMAGE_FILE_EXTENSIONS={".png", ".jpg", ".jpeg"},
            FILE_ENCODING="utf-8",
            image_description_section_heading="## Extracted Image Descriptions",
            image_description_heading="**[BEGIN]**",
            image_description_end="**[END]**"
        )

    def test_mineru_image_path_compatibility(self) -> None:
        """
        Regression test for MinerU-style image paths (images/subfolder).
        Verifies that list_extracted_images_for_output_file finds them and
        insert_image_descriptions_to_text_file matches them.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output_file = temp_path / "document.md"

            # MinerU typically creates an 'images' subfolder
            images_dir = temp_path / "images"
            images_dir.mkdir()
            image1 = images_dir / "fig1.png"
            image1.write_bytes(b"fake image")

            # MinerU markdown output uses relative paths to the images folder
            content = "# My Document\n\nRefer to ![](images/fig1.png) for details.\n"
            output_file.write_text(content, encoding="utf-8")

            # 1. Verify discovery
            discovered_images = list_extracted_images_for_output_file(self.app_config, output_file)
            self.assertIn(image1, discovered_images)

            # 2. Verify insertion
            descriptions = [(image1, "Description for fig1")]
            success = insert_image_descriptions_to_text_file(
                app_config=self.app_config,
                output_file_path=output_file,
                image_descriptions=descriptions
            )

            self.assertTrue(success)
            updated_content = output_file.read_text(encoding="utf-8")

            # Should match ![](images/fig1.png) followed by the description
            # The regex handles the images/ prefix
            self.assertIn("![](images/fig1.png)\n\n> **[BEGIN]**\n> Description for fig1\n> **[END]**", updated_content)

    def test_two_column_reading_order_preservation(self) -> None:
        """
        Regression test for two-column reading order.
        Simulates MinerU output for a two-column layout and verifies
        deterministic anchor matching.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output_file = temp_path / "two_column.md"

            # Simulated MinerU markdown from a two-column PDF
            # Reading order: Left col (P1, Img1), Right col (P2, Img2)
            content = (
                "Left column paragraph.\n\n"
                "![](images/left_img.png)\n\n"
                "Right column paragraph.\n\n"
                "![](images/right_img.png)\n"
            )
            output_file.write_text(content, encoding="utf-8")

            images_dir = temp_path / "images"
            images_dir.mkdir()
            (images_dir / "left_img.png").write_bytes(b"img1")
            (images_dir / "right_img.png").write_bytes(b"img2")

            descriptions = [
                (images_dir / "right_img.png", "Right Description"),
                (images_dir / "left_img.png", "Left Description"),
            ]

            # Insert (order of descriptions in list shouldn't matter for in-place insertion)
            insert_image_descriptions_to_text_file(
                app_config=self.app_config,
                output_file_path=output_file,
                image_descriptions=descriptions
            )

            updated_content = output_file.read_text(encoding="utf-8")

            # Verify they are inserted at correct anchors
            left_pos = updated_content.find("Left Description")
            right_pos = updated_content.find("Right Description")

            self.assertNotEqual(left_pos, -1)
            self.assertNotEqual(right_pos, -1)
            # Left should come before right in the final document
            self.assertTrue(left_pos < right_pos, "Left column description should precede right column description")

if __name__ == "__main__":
    unittest.main()
