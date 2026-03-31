import unittest
from utils import LanguageProcessor
from langdetect import DetectorFactory

class TestLanguageInference(unittest.TestCase):
    def setUp(self):
        # Reset seed for each test for determinism
        DetectorFactory.seed = 0

    def test_infer_english(self):
        text = "This is a simple English sentence intended for language detection testing. It should be long enough to provide a clear signal."
        self.assertEqual(LanguageProcessor.infer_output_language(text), "en")

    def test_infer_german(self):
        text = "Dies ist ein einfacher deutscher Satz, der für Tests zur Spracherkennung gedacht ist. Er sollte lang genug sein, um ein klares Signal zu geben."
        self.assertEqual(LanguageProcessor.infer_output_language(text), "de")

    def test_infer_french(self):
        text = "Ceci est une simple phrase en français destinée à tester la détection de la langue. Elle devrait être assez longue pour fournir un signal clair."
        self.assertEqual(LanguageProcessor.infer_output_language(text), "fr")

    def test_infer_spanish(self):
        text = "Esta es una oración simple en español destinada a probar la detección de idiomas. Debe ser lo suficientemente larga como para proporcionar una señal clara."
        self.assertEqual(LanguageProcessor.infer_output_language(text), "es")

    def test_infer_short_text_fallback(self):
        # Very short text should fallback to English
        text = "Short text."
        self.assertEqual(LanguageProcessor.infer_output_language(text), "en")

    def test_infer_unsupported_language_fallback(self):
        # Swahili is not in our mapped languages
        # Even if detected as 'sw', it should fallback to 'en'
        text = "Habari gani? Hii ni sentensi ya Kiswahili kwa ajili ya kujaribu utambuzi wa lugha."
        result = LanguageProcessor.infer_output_language(text)
        self.assertEqual(result, "en")

    def test_infer_mixed_language_deterministic(self):
        # Mixed English and German
        text = "This is English. Dies ist Deutsch. " * 10
        # Should be deterministic due to seed
        lang1 = LanguageProcessor.infer_output_language(text)
        DetectorFactory.seed = 0
        lang2 = LanguageProcessor.infer_output_language(text)
        self.assertEqual(lang1, lang2)

    def test_resolve_language_name(self):
        self.assertEqual(LanguageProcessor.resolve_language_name("en"), "English")
        self.assertEqual(LanguageProcessor.resolve_language_name("de"), "German")
        self.assertEqual(LanguageProcessor.resolve_language_name("unknown"), "English")

if __name__ == "__main__":
    unittest.main()
