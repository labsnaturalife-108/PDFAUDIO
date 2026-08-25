import unittest
from pathlib import Path
from stress_dict import StressDictionary
from chunker import TextChunker
from extractor import DocumentExtractor

class TestAudiobookPipeline(unittest.TestCase):
    def setUp(self):
        self.dict = StressDictionary()

    def test_stress_dictionary_replacements(self):
        text = "Арджуна и Кришна пришли на поле Курукшетра. арджуна внимательно слушал."
        stressed = self.dict.apply(text)
        self.assertIn("Арджу́на", stressed)
        self.assertIn("Кри́шна", stressed)
        self.assertIn("Курукше́тра", stressed)
        self.assertIn("арджу́на", stressed)  # preserves lower case
        self.assertIn("внима́тельно", stressed)

    def test_chunker_basic(self):
        text = "Первое предложение! Второе предложение? Третье предложение. Четвертое предложение."
        chunks = TextChunker.split_into_chunks(text, max_chunk_len=45)
        self.assertTrue(len(chunks) >= 2)
        # Ensure all sentences are retained
        recombined = " ".join(chunks)
        self.assertIn("Первое предложение!", recombined)
        self.assertIn("Четвертое предложение.", recombined)

    def test_text_cleaner(self):
        raw = "Слово1-\nперенос   лишние   пробелы.\xad"
        cleaned = DocumentExtractor.clean_text(raw)
        self.assertEqual(cleaned, "Слово1перенос лишние пробелы.")

if __name__ == "__main__":
    unittest.main()
