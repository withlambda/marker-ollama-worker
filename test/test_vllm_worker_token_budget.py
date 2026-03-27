"""Tests for vLLM chunk request token budgeting."""

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vllm_worker import VllmWorker
from settings import VllmSettings, GlobalConfig


def _make_worker(max_model_len: int = 100) -> VllmWorker:
    """Create a worker configured for token-budget tests with real settings models."""
    os.environ["VOLUME_ROOT_MOUNT_PATH"] = "/tmp"
    os.environ["VRAM_GB_TOTAL"] = "24"
    settings = VllmSettings(
        app_config=GlobalConfig(),
        vllm_vram_gb_model=4,
        vllm_model="stub-model",
        vllm_host="127.0.0.1",
        vllm_port=8001,
        vllm_chunk_size=1024,
        vllm_max_model_len=max_model_len,
        vllm_max_retries=0,
        vllm_retry_delay=0.01,
        vllm_shutdown_grace_period=10,
        vllm_health_check_interval=2.0,
        vllm_chat_completion_token_safety_margin=64,
        vllm_min_completion_tokens=1,
        vllm_image_description_max_tokens=1024,
        vllm_tiktoken_encoding_name="gpt2",
        vllm_temperature_text_chunk_correction=0.0,
        vllm_temperature_image_description=0.0,
    )
    settings.vllm_chunk_output_formatting_instruction = "Return only JSON with a text field."
    settings.vllm_image_description_output_formatting_instruction = "Return only JSON with a text field."
    settings.vllm_output_json_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }
    worker = VllmWorker(settings=settings)

    response = types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=types.SimpleNamespace(content='{"text": "corrected"}'))]
    )
    worker._client = types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=AsyncMock(return_value=response))
        )
    )
    return worker


class TestVllmWorkerChunkTokenBudget(unittest.IsolatedAsyncioTestCase):
    """Validate chunk processing request construction against context limits."""

    def test_process_text_uses_prompt_aware_chunk_size(self):
        """process_text should reduce chunk_size by prompt/context budget before chunking."""
        worker = _make_worker(max_model_len=100)

        with patch.object(worker, "_count_tokens", side_effect=[10, 2]), patch.object(
            worker,
            "_chunk_text",
            return_value=["alpha"],
        ) as chunk_mock, patch.object(
            worker,
            "_process_chunks_async",
            new=AsyncMock(return_value=["corrected"]),
        ):
            result = worker.process_text("original", "system", 1)

        self.assertEqual(result, "corrected")
        chunk_mock.assert_called_once_with("original", 10)

    def test_effective_chunk_size_uses_input_output_ratio(self):
        """Chunk budget should be computed with the ratio formula using context budget / (1 + r)."""
        worker = _make_worker(max_model_len=200)

        with patch.object(worker, "_count_tokens", side_effect=[30, 30]):
            effective_chunk_size = worker._compute_effective_chunk_size("system", r=1.0)

        expected_context_budget = (
            worker.settings.vllm_max_model_len
            - 30
            - 30
            - worker.settings.vllm_chat_completion_token_safety_margin
        )
        expected_chunk_size = min(worker.settings.vllm_chunk_size, int(expected_context_budget / 2.0))
        self.assertEqual(effective_chunk_size, expected_chunk_size)

    def test_process_text_returns_original_when_prompt_exhausts_chunk_budget(self):
        """process_text should skip chunking/API work when prompt leaves no context room."""
        worker = _make_worker(max_model_len=100)

        with patch.object(worker, "_count_tokens", return_value=99), patch.object(
            worker,
            "_chunk_text",
            return_value=["should-not-be-used"],
        ) as chunk_mock, patch.object(
            worker,
            "_process_chunks_async",
            new=AsyncMock(return_value=["should-not-be-used"]),
        ) as process_mock:
            result = worker.process_text("original", "system", 1)

        self.assertEqual(result, "original")
        chunk_mock.assert_not_called()
        process_mock.assert_not_called()

    async def test_chunk_request_caps_completion_tokens_by_prompt_size(self):
        """Request should use a completion budget smaller than full context when prompt is non-empty."""
        worker = _make_worker(max_model_len=100)

        with patch.object(worker, "_count_tokens", side_effect=[10, 20]):
            result = await worker._process_single_chunk_async("chunk", "system", 0)

        self.assertEqual(result, "corrected")
        create_mock = worker._client.chat.completions.create
        self.assertEqual(create_mock.await_count, 1)
        self.assertLess(create_mock.await_args.kwargs["max_tokens"], worker.settings.vllm_max_model_len)
        self.assertGreater(create_mock.await_args.kwargs["max_tokens"], 0)

    async def test_chunk_processing_skips_api_call_when_prompt_exceeds_context(self):
        """If prompt already exhausts context, worker should return original chunk without API call."""
        worker = _make_worker(max_model_len=100)

        with patch.object(worker, "_count_tokens", side_effect=[80, 40]):
            result = await worker._process_single_chunk_async("original", "system", 0)

        self.assertEqual(result, "original")
        create_mock = worker._client.chat.completions.create
        self.assertEqual(create_mock.await_count, 0)

    async def test_image_description_uses_template_only_in_system_prompt(self):
        """Image description should not duplicate prompt template in user instruction."""
        worker = _make_worker(max_model_len=100)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            tmp_file.write(b"fake-image-bytes")
            image_path = Path(tmp_file.name)

        prompt_template = "Custom image-description instructions"

        try:
            with patch.object(worker, "_count_tokens", return_value=1) as token_counter, patch.object(
                worker.image_token_calculator,
                "calculate_image_tokens",
                return_value=1,
            ):
                result = await worker._describe_single_image_async(image_path, prompt_template, image_index=0)
        finally:
            image_path.unlink(missing_ok=True)

        self.assertEqual(result, "corrected")
        create_mock = worker._client.chat.completions.create
        self.assertEqual(create_mock.await_count, 1)

        messages = create_mock.await_args.kwargs["messages"]
        self.assertIn(prompt_template, messages[0]["content"])
        self.assertEqual(messages[1]["content"][1]["text"], "### IMAGE TO DESCRIBE\n")
        self.assertNotIn(prompt_template, messages[1]["content"][1]["text"])

        self.assertEqual(token_counter.call_count, 1)
        _, user_instruction = token_counter.call_args.args
        self.assertEqual(user_instruction, "### IMAGE TO DESCRIBE\n")

    async def test_image_description_skips_api_call_when_prompt_exceeds_context(self):
        """Image description should return fallback when prompt leaves no completion budget."""
        worker = _make_worker(max_model_len=100)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            tmp_file.write(b"fake-image-bytes")
            image_path = Path(tmp_file.name)

        try:
            with patch.object(worker, "_count_tokens", return_value=80), patch.object(
                worker.image_token_calculator,
                "calculate_image_tokens",
                return_value=40,
            ):
                result = await worker._describe_single_image_async(image_path, "system", image_index=0)
        finally:
            image_path.unlink(missing_ok=True)

        self.assertEqual(result, "> **Image Description:** [Description unavailable]")
        create_mock = worker._client.chat.completions.create
        self.assertEqual(create_mock.await_count, 0)


if __name__ == "__main__":
    unittest.main()
