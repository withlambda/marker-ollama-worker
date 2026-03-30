import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from vllm_worker import VllmWorker
from settings import VllmSettings, GlobalConfig

class TestVllmWorkerLanguageAware(unittest.TestCase):
    def setUp(self):
        # Create a mock GlobalConfig that behaves enough like a Pydantic model
        self.app_config = MagicMock(spec=GlobalConfig)
        self.app_config.vram_gb_total = 16
        self.app_config.vram_gb_reserve = 4
        self.app_config.vram_gb_per_token_factor = 0.0001
        self.app_config.block_correction_prompts_library = {}

        # We need a real-ish VllmSettings for VllmWorker
        self.settings = VllmSettings(
            app_config=self.app_config,
            vllm_model="test-model",
            vllm_vram_gb_model=4,
            vllm_port=8000,
            vllm_max_model_len=1024
        )
        # Mock the AsyncOpenAI client
        self.mock_client = MagicMock()
        self.mock_client.chat = MagicMock()
        self.mock_client.chat.completions = MagicMock()
        self.mock_client.chat.completions.create = AsyncMock()

    @patch('vllm_worker.openai.AsyncOpenAI')
    @patch('vllm_worker.VllmWorker.start_server')
    def test_describe_single_image_with_language(self, mock_start, mock_openai_class):
        mock_openai_class.return_value = self.mock_client
        worker = VllmWorker(self.settings)
        worker._client = self.mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"text": "This is a description in German."}'
        self.mock_client.chat.completions.create.return_value = mock_response

        image_path = Path("test.png")
        # Mock image read
        with patch.object(Path, "read_bytes", return_value=b"fake-image-data"), patch.object(
            worker.image_token_calculator,
            "calculate_image_tokens",
            return_value=128,
        ), patch.object(
            worker,
            "_compute_max_completion_tokens",
            return_value=128,
        ):
            import asyncio
            description = asyncio.run(worker._describe_single_image_async(
                image_path,
                prompt_template=None,
                image_index=0,
                target_language="German"
            ))

        self.assertEqual(description, "This is a description in German.")

        # Check if the system prompt was updated correctly
        call_args = self.mock_client.chat.completions.create.call_args
        messages = call_args.kwargs['messages']
        system_msg = next(m for m in messages if m['role'] == 'system')
        self.assertIn("You must answer in German.", system_msg['content'])

    @patch('vllm_worker.openai.AsyncOpenAI')
    @patch('vllm_worker.VllmWorker.start_server')
    def test_describe_single_image_without_language(self, mock_start, mock_openai_class):
        mock_openai_class.return_value = self.mock_client
        worker = VllmWorker(self.settings)
        worker._client = self.mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"text": "English description."}'
        self.mock_client.chat.completions.create.return_value = mock_response

        image_path = Path("test.png")
        with patch.object(Path, "read_bytes", return_value=b"fake-image-data"), patch.object(
            worker.image_token_calculator,
            "calculate_image_tokens",
            return_value=128,
        ), patch.object(
            worker,
            "_compute_max_completion_tokens",
            return_value=128,
        ):
            import asyncio
            description = asyncio.run(worker._describe_single_image_async(
                image_path,
                prompt_template=None,
                image_index=0,
                target_language=None
            ))

        self.assertEqual(description, "English description.")
        call_args = self.mock_client.chat.completions.create.call_args
        messages = call_args.kwargs['messages']
        system_msg = next(m for m in messages if m['role'] == 'system')
        self.assertNotIn("Respond in", system_msg['content'])

if __name__ == "__main__":
    unittest.main()
