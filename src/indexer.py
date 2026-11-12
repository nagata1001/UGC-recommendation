from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np

from .config import INDEX_DIR
from .encoder import MultimodalEncoder
from .index_store import FaissStore
from .ocr import OCRExtractor


def read_records(input_path: Path) -> Iterable[Dict]:
    seen = set()
    with input_path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            item_id = str(row.get("id", "")).strip()
            if not item_id:
                raise ValueError(f"第 {line_number} 行缺少 id")
            if item_id in seen:
                raise ValueError(f"id 重复：{item_id}")
            seen.add(item_id)
            text = str(row.get("text", "")).strip()
            image_value = str(row.get("image", "")).strip()
            image_path: Optional[Path] = None
            if image_value:
                candidate = Path(image_value)
                image_path = candidate if candidate.is_absolute() else input_path.parent / candidate
                image_path = image_path.resolve()
                if not image_path.exists():
                    raise FileNotFoundError(f"图片不存在：{image_path}")
            if not text and image_path is None:
                raise ValueError(f"第 {line_number} 行既没有文本也没有图片")
            yield {"id": item_id, "text": text, "image_path": image_path, "source": row}


def build_index(input_path: Path, use_ocr: bool = False, device: Optional[str] = None) -> int:
    encoder = MultimodalEncoder(device=device)
    ocr = OCRExtractor() if use_ocr else None
    vectors: List[np.ndarray] = []
    metadata: List[Dict] = []

    for record in read_records(input_path):
        text = record["text"]
        image_path = record["image_path"]
        ocr_text = ocr.extract(image_path) if ocr is not None and image_path is not None else ""
        combined_text = " ".join(value for value in (text, ocr_text) if value).strip()
        vector = encoder.encode_item(text=combined_text, image_path=image_path)
        vectors.append(vector)
        metadata.append(
            {
                "id": record["id"],
                "text": text,
                "ocr_text": ocr_text,
                "image": str(image_path) if image_path else "",
            }
        )

    if not vectors:
        raise ValueError("输入文件中没有有效数据")
    store = FaissStore(INDEX_DIR / "ugc.faiss", INDEX_DIR / "ugc_metadata.jsonl")
    store.build(np.stack(vectors), metadata)
    store.save()
    return len(vectors)

