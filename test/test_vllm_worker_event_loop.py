"""
Regression tests for VllmWorker sync APIs when an asyncio loop is already running.
"""

import sys
import types
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vllm_worker import VllmWorker


def _make_worker() -> VllmWorker:
    """Create a lightweight worker with only the settings needed by these tests."""
    settings = types.SimpleNamespace(
        vllm_model="stub-model",
        vllm_host="127.0.0.1",
        vllm_port=8001,
        vllm_chunk_size=1024,
        vllm_max_model_len=8192,
        vllm_chat_completion_token_safety_margin=64,
    )
    return VllmWorker(settings=settings)


class TestVllmWorkerEventLoopBridge(unittest.IsolatedAsyncioTestCase):
    """Ensure sync worker APIs remain callable from contexts with an active event loop."""

    async def test_process_text_from_running_loop(self):
        """process_text should succeed without loop re-entry errors or un-awaited coroutine warnings."""
        worker = _make_worker()

        async def fake_process(_chunks, _prompt, _max_workers):
            return ["fixed-alpha", "fixed-beta"]

        with patch.object(worker, "_chunk_text", return_value=["alpha", "beta"]), patch.object(
            worker,
            "_process_chunks_async",
            side_effect=fake_process,
        ):
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always", RuntimeWarning)
                result = worker.process_text("ignored", "prompt", 4)

        self.assertEqual(result, "fixed-alpha\n\nfixed-beta")
        self.assertFalse(
            any("was never awaited" in str(item.message) for item in captured),
            "No un-awaited coroutine warning should be emitted",
        )

    async def test_describe_images_from_running_loop(self):
        """describe_images should succeed from async context and preserve non-empty results order."""
        worker = _make_worker()
        image_paths = [Path("/tmp/a.png"), Path("/tmp/b.png")]

        async def fake_describe(_paths, _prompt, _max_workers):
            return ["desc-a", None]

        with patch.object(worker, "_describe_images_async", side_effect=fake_describe):
            descriptions = worker.describe_images(image_paths, "prompt", 2)

        self.assertEqual(descriptions, [(image_paths[0], "desc-a")])


if __name__ == "__main__":
    unittest.main()
