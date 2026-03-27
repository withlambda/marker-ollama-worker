"""Tests for markdown chunking behavior in ``VllmWorker``."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vllm_worker import VllmWorker
from settings import VllmSettings, GlobalConfig


def _make_worker(chunk_size: int = 100) -> VllmWorker:
    """Create a worker configured for chunking tests with real settings models."""
    os.environ["VOLUME_ROOT_MOUNT_PATH"] = "/tmp"
    os.environ["VRAM_GB_TOTAL"] = "24"
    settings = VllmSettings(
        app_config=GlobalConfig(),
        vllm_vram_gb_model=4,
        vllm_model="stub-model",
        vllm_host="127.0.0.1",
        vllm_port=8001,
        vllm_chunk_size=chunk_size,
        vllm_tiktoken_encoding_name="gpt2",
    )
    return VllmWorker(settings=settings)


class TestVllmWorkerChunking(unittest.TestCase):
    """Validate langchain-backed chunk splitting behavior."""

    def test_chunk_text_uses_langchain_splitter_for_blocks(self):
        """Markdown blocks should be split via RecursiveCharacterTextSplitter without overlap."""
        worker = _make_worker(chunk_size=100)

        splitter_mock = MagicMock()
        # Mock split_text to return different results based on input
        def mock_split(text):
            if text == "small":
                return ["small"]
            return ["large-part-1", "large-part-2"]

        splitter_mock.split_text.side_effect = mock_split

        with patch.object(worker, "_split_into_blocks", return_value=["small", "large"]), \
             patch("vllm_worker.RecursiveCharacterTextSplitter.from_tiktoken_encoder", return_value=splitter_mock) as from_tiktoken_mock:

            chunks = worker._chunk_text("ignored", chunk_size=100)

        # In the new simplified logic, blocks are NOT packed.
        self.assertEqual(chunks, ["small", "large-part-1", "large-part-2"])

        # Verify splitter initialization
        from_tiktoken_mock.assert_called_once()
        _, kwargs = from_tiktoken_mock.call_args
        self.assertEqual(kwargs["chunk_size"], 100)
        self.assertEqual(kwargs["chunk_overlap"], 0)
        self.assertEqual(kwargs["encoding_name"], "gpt2")

    def test_chunk_text_raises_when_splitter_fails(self):
        """Errors from token splitter must propagate for required dependencies."""
        worker = _make_worker(chunk_size=50)

        with patch("vllm_worker.RecursiveCharacterTextSplitter.from_tiktoken_encoder") as from_tiktoken_mock, \
             patch.object(worker, "_split_into_blocks", return_value=["oversized"]):

            splitter_mock = MagicMock()
            splitter_mock.split_text.side_effect = RuntimeError("split failed")
            from_tiktoken_mock.return_value = splitter_mock

            with self.assertRaisesRegex(RuntimeError, "split failed"):
                worker._chunk_text("ignored", chunk_size=50)


if __name__ == "__main__":
    unittest.main()
