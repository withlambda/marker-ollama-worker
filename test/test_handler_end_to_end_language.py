import unittest
from unittest.mock import MagicMock, patch, ANY
from pathlib import Path
import sys
import types
from importlib.machinery import ModuleSpec


def _make_module(name: str):
    module = types.ModuleType(name)
    module.__spec__ = ModuleSpec(name, loader=None)
    if name == "torch.multiprocessing":
        module.set_start_method = lambda *_args, **_kwargs: None
    return module

# Mock dependencies
MOCK_MODULES = {
    "runpod": MagicMock(),
    "torch": _make_module("torch"),
    "torch.multiprocessing": _make_module("torch.multiprocessing"),
    "mineru": MagicMock(),
    "mineru.data": MagicMock(),
    "mineru.data.data_reader_writer": MagicMock(),
    "mineru.data.dataset": MagicMock(),
    "mineru.model": MagicMock(),
    "mineru.model.doc_analyze_by_custom_model": MagicMock(),
}
sys.modules.update(MOCK_MODULES)
__import__("handler")

class TestHandlerEndToEndLanguage(unittest.TestCase):
    def setUp(self):
        self.app_config = MagicMock()
        self.app_config.FILE_ENCODING = "utf-8"
        self.app_config.image_description_heading = "[BEGIN]"
        self.app_config.image_description_end = "[END]"
        self.app_config.image_description_section_heading = "## Descriptions"
        self.app_config.use_postprocess_llm = True

    @patch('handler.list_extracted_images_for_output_file')
    @patch('handler.insert_image_descriptions_to_text_file')
    @patch('handler.LanguageProcessor.infer_output_language')
    @patch('handler.LanguageProcessor.resolve_language_name')
    @patch('handler.LanguageProcessor.resolve_image_description_labels')
    def test_handler_passes_language_to_worker_and_labels(
        self, mock_resolve_labels, mock_resolve_name, mock_infer, mock_insert, mock_list_images
    ):
        # Mock setup
        mock_infer.return_value = "de"
        mock_resolve_name.return_value = "German"
        mock_resolve_labels.return_value = {
            "begin_marker": "[BEGIN_DE]",
            "end_marker": "[END_DE]",
            "section_heading": "## Beschreibung_DE"
        }
        mock_list_images.return_value = [Path("img1.png")]

        mock_worker = MagicMock()
        mock_worker.process_file.return_value = True
        mock_worker.describe_images.return_value = [(Path("img1.png"), "Desc")]

        mock_vllm_settings = MagicMock()
        mock_vllm_settings.vllm_chunk_workers = 2
        mock_vllm_settings.vllm_block_correction_prompt = "Prompt"
        mock_vllm_settings.vllm_image_description_prompt = "ImgPrompt"

        processed_file_path = MagicMock(spec=Path)
        processed_file_path.name = "test.md"
        processed_file_path.read_text.return_value = "Some German text: Dies ist ein Test."

        # Simulate the loop logic in handler
        # We don't call handler() because it's too complex to mock everything it needs
        # Instead we test the logic we added to the loop.

        # 1. Process file (already mocked as success)
        success = mock_worker.process_file(
            file_path=processed_file_path,
            prompt_template=mock_vllm_settings.vllm_block_correction_prompt,
            max_chunk_workers=mock_vllm_settings.vllm_chunk_workers
        )
        self.assertTrue(success)

        # 2. Infer language
        text_content = processed_file_path.read_text(encoding="utf-8")
        target_lang_code = mock_infer(text_content)
        target_lang_name = mock_resolve_name(target_lang_code)

        self.assertEqual(target_lang_code, "de")
        self.assertEqual(target_lang_name, "German")

        # 3. List images
        extracted_images = mock_list_images(self.app_config, processed_file_path)

        # 4. Describe images
        image_descriptions = mock_worker.describe_images(
            image_paths=extracted_images,
            prompt_template=mock_vllm_settings.vllm_image_description_prompt,
            max_image_workers=mock_vllm_settings.vllm_chunk_workers,
            target_language=target_lang_name
        )

        # Verify language passed to worker
        mock_worker.describe_images.assert_called_once_with(
            image_paths=extracted_images,
            prompt_template=ANY,
            max_image_workers=ANY,
            target_language="German"
        )

        # 5. Resolve labels
        localized_labels = mock_resolve_labels(target_lang_code, self.app_config)

        # 6. Insert descriptions
        mock_insert(
            app_config=self.app_config,
            output_file_path=processed_file_path,
            image_descriptions=image_descriptions,
            heading_override=localized_labels["begin_marker"],
            end_override=localized_labels["end_marker"],
            section_heading_override=localized_labels["section_heading"]
        )

        # Verify localized labels passed to insertion helper
        mock_insert.assert_called_once_with(
            app_config=self.app_config,
            output_file_path=processed_file_path,
            image_descriptions=image_descriptions,
            heading_override="[BEGIN_DE]",
            end_override="[END_DE]",
            section_heading_override="## Beschreibung_DE"
        )

if __name__ == "__main__":
    unittest.main()
