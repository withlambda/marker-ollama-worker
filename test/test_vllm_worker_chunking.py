"""Tests for markdown chunking behavior in ``VllmWorker``."""

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vllm_worker import VllmWorker


def _make_worker(chunk_size: int = 100) -> VllmWorker:
    """Create a lightweight worker configured for chunking tests."""
    settings = types.SimpleNamespace(
        vllm_model="stub-model",
        vllm_host="127.0.0.1",
        vllm_port=8001,
        vllm_chunk_size=chunk_size,
        vllm_langchain_chunk_overlap_ratio=0.1,
        vllm_langchain_min_chunk_overlap=32,
        vllm_langchain_max_chunk_overlap=256,
    )
    return VllmWorker(settings=settings)


class TestVllmWorkerChunking(unittest.TestCase):
    """Validate mandatory langchain-backed chunk splitting behavior."""

    def test_chunk_text_uses_langchain_splitter_for_oversized_blocks(self):
        """Oversized markdown blocks should be split via token splitter with overlap."""
        worker = _make_worker(chunk_size=100)

        splitter_inits = []

        class FakeTokenTextSplitter:
            def __init__(self, chunk_size, chunk_overlap, encoding_name):
                splitter_inits.append((chunk_size, chunk_overlap, encoding_name))

            def split_text(self, _text):
                return ["large-part-1", "large-part-2"]

        with patch.object(worker, "_split_into_blocks", return_value=["small", "large"]), patch.object(
            worker,
            "_count_tokens",
            side_effect=[10, 180],
        ), patch("vllm_worker.TokenTextSplitter", FakeTokenTextSplitter):
            chunks = worker._chunk_text("ignored", chunk_size=100)

        self.assertEqual(chunks, ["small", "large-part-1", "large-part-2"])
        self.assertEqual(splitter_inits, [(100, 32, "cl100k_base")])

    def test_split_large_block_raises_when_splitter_fails(self):
        """Errors from token splitter must propagate for required dependencies."""
        worker = _make_worker(chunk_size=50)

        class FailingTokenTextSplitter:
            def __init__(self, chunk_size, chunk_overlap, encoding_name):
                self.chunk_size = chunk_size
                self.chunk_overlap = chunk_overlap
                self.encoding_name = encoding_name

            def split_text(self, _text):
                raise RuntimeError("split failed")

        with patch("vllm_worker.TokenTextSplitter", FailingTokenTextSplitter), patch.object(
            worker,
            "_split_large_block",
            return_value=["fallback"],
        ) as fallback_mock:
            with self.assertRaisesRegex(RuntimeError, "split failed"):
                worker._split_large_block_with_overlap("oversized", 50)

        fallback_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
