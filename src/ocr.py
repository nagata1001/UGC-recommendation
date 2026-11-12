from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, List


def _plain_result(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple, str, int, float, bool)) or value is None:
        return value
    candidate = getattr(value, "json", None)
    if callable(candidate):
        candidate = candidate()
    if candidate is not None:
        if isinstance(candidate, str):
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                return candidate
        return candidate
    return value.__dict__ if hasattr(value, "__dict__") else str(value)


def _collect_recognized_text(value: Any) -> List[str]:
    value = _plain_result(value)
    found: List[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"rec_texts", "texts"} and isinstance(child, (list, tuple)):
                found.extend(str(item).strip() for item in child if str(item).strip())
            elif key in {"rec_text", "text"} and isinstance(child, str) and child.strip():
                found.append(child.strip())
            else:
                found.extend(_collect_recognized_text(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.extend(_collect_recognized_text(child))
    return found


def _is_meaningful_text(value: str) -> bool:
    """Discard OCR noise made only of punctuation or separators."""
    return bool(re.search(r"[0-9A-Za-z\u4e00-\u9fff]", value))


class OCRExtractor:
    def __init__(self) -> None:
        from paddleocr import PaddleOCR

        self.engine = PaddleOCR(
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name="PP-OCRv5_mobile_rec",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

    def extract(self, image_path: Path) -> str:
        if hasattr(self.engine, "predict"):
            result = self.engine.predict(input=str(image_path))
        else:
            result = self.engine.ocr(str(image_path))
        texts = [text for text in _collect_recognized_text(result) if _is_meaningful_text(text)]
        return " ".join(dict.fromkeys(texts))

