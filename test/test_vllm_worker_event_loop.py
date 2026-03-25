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


def _install_dependency_stubs() -> None:
    """Install lightweight module stubs for optional external dependencies."""
    settings_module = types.ModuleType("settings")

    class DummyVllmSettings:
        pass

    settings_module.VllmSettings = DummyVllmSettings
    sys.modules.setdefault("settings", settings_module)

    httpx_module = types.ModuleType("httpx")
    httpx_module.ConnectError = Exception
    httpx_module.ReadError = Exception
    httpx_module.TimeoutException = Exception
    httpx_module.HTTPStatusError = Exception
    httpx_module.Client = object
    sys.modules.setdefault("httpx", httpx_module)

    tiktoken_module = types.ModuleType("tiktoken")
    dummy_encoding = types.SimpleNamespace(encode=lambda text: list(text))
    tiktoken_module.encoding_for_model = lambda *_args, **_kwargs: dummy_encoding
    tiktoken_module.get_encoding = lambda *_args, **_kwargs: dummy_encoding
    sys.modules.setdefault("tiktoken", tiktoken_module)

    openai_module = types.ModuleType("openai")
    openai_module.AsyncOpenAI = object
    openai_module.RateLimitError = Exception
    openai_module.InternalServerError = Exception
    openai_module.APIConnectionError = Exception
    openai_module.APITimeoutError = Exception
    sys.modules.setdefault("openai", openai_module)

    openai_types_module = types.ModuleType("openai.types")
    sys.modules.setdefault("openai.types", openai_types_module)

    openai_types_chat_module = types.ModuleType("openai.types.chat")
    openai_types_chat_module.ChatCompletionUserMessageParam = dict
    openai_types_chat_module.ChatCompletionSystemMessageParam = dict
    openai_types_chat_module.ChatCompletionContentPartImageParam = dict
    openai_types_chat_module.ChatCompletionContentPartTextParam = dict
    sys.modules.setdefault("openai.types.chat", openai_types_chat_module)

    openai_types_chat_image_module = types.ModuleType(
        "openai.types.chat.chat_completion_content_part_image_param"
    )
    openai_types_chat_image_module.ImageURL = dict
    sys.modules.setdefault(
        "openai.types.chat.chat_completion_content_part_image_param",
        openai_types_chat_image_module,
    )


_install_dependency_stubs()

from vllm_worker import VllmWorker


def _make_worker() -> VllmWorker:
    """Create a lightweight worker with only the settings needed by these tests."""
    settings = types.SimpleNamespace(
        vllm_model="stub-model",
        vllm_host="127.0.0.1",
        vllm_port=8001,
        vllm_chunk_size=1024,
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
