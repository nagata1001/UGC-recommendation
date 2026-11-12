import unittest

from src.ocr import _is_meaningful_text


class OCRFilterTest(unittest.TestCase):
    def test_rejects_punctuation_only_noise(self) -> None:
        self.assertFalse(_is_meaningful_text("-"))
        self.assertFalse(_is_meaningful_text("..."))

    def test_accepts_chinese_and_alphanumeric_text(self) -> None:
        self.assertTrue(_is_meaningful_text("机器学习"))
        self.assertTrue(_is_meaningful_text("UGC-2026"))


if __name__ == "__main__":
    unittest.main()
