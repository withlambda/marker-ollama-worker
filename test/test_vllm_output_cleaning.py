import unittest
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vllm_worker import VllmWorker

class TestVllmOutputCleaning(unittest.TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(
            vllm_model="test-model",
            vllm_host="localhost",
            vllm_port=8000
        )
        self.worker = VllmWorker(self.settings)

    def test_clean_think_blocks(self):
        text = "<think>\nSome reasoning here\n</think>\nActual content"
        # Assuming we add _clean_llm_output
        cleaned = self.worker._clean_llm_output(text)
        self.assertEqual(cleaned, "Actual content")

    def test_clean_multiple_think_blocks(self):
        text = "<think>R1</think> Content 1 <think>R2</think> Content 2"
        cleaned = self.worker._clean_llm_output(text)
        self.assertEqual(cleaned.strip(), "Content 1  Content 2")

    def test_clean_unclosed_think_block(self):
        text = "<think>Reasoning... Actual content"
        cleaned = self.worker._clean_llm_output(text)
        # If unclosed, we should probably still try to remove the beginning or handle it gracefully
        # For now let's see how we implement it.
        pass

    def test_clean_conversational_prefixes(self):
        prefixes = [
            "Okay, let's tackle this.",
            "Certainly! Here is the corrected text:",
            "Got it, let's look at the image.",
            "Sure, I can help with that.",
            "I understood the instructions.",
            "Let me structure it."
        ]
        for p in prefixes:
            text = f"{p}\n\nActual content"
            cleaned = self.worker._clean_llm_output(text)
            self.assertEqual(cleaned, "Actual content", f"Failed for prefix: {p}")

    def test_clean_nested_think_with_prefix(self):
        text = "Okay, I'll help.\n<think>\nReasoning\n</think>\nActual content"
        cleaned = self.worker._clean_llm_output(text)
        self.assertEqual(cleaned, "Actual content")

    def test_real_world_sample_from_issue(self):
        # Sample from the issue description style
        text = """Okay, let's tackle this OCR correction task. The user wants me to fix errors in a 19th-century German text while preserving historical orthography.

First, I need to carefully analyze the given text. It's a bibliography entry about König Ottotar's history, with page numbers and historical references. The OCR has messed up several German orthography conventions from that era.

Hmm... the most obvious issues jump out immediately:
- "Thüringen" is written as "Thüringen" which is correct, but "Thür" should be "Thür" (with ü)
- "sür" clearly should be "für" (f instead of s)

<think>
Wait, I should check the word...
</think>

Corrected text:
König Ottotars Feldzug an ben Rhein (1198) —428."""
        cleaned = self.worker._clean_llm_output(text)
        # We want to get rid of the intro and the "Corrected text:" label too if possible
        self.assertTrue(cleaned.startswith("König Ottotars"))
        self.assertNotIn("Okay, let's tackle", cleaned)
        self.assertNotIn("<think>", cleaned)
        self.assertNotIn("Corrected text:", cleaned)

if __name__ == "__main__":
    unittest.main()
