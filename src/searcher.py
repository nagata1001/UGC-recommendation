from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .config import INDEX_DIR
from .encoder import MultimodalEncoder
from .index_store import FaissStore


class Searcher:
    def __init__(self, device: Optional[str] = None) -> None:
        self.encoder = MultimodalEncoder(device=device)
        self.store = FaissStore(INDEX_DIR / "ugc.faiss", INDEX_DIR / "ugc_metadata.jsonl")
        self.store.load()

    def search(self, text: str = "", image_path: Optional[Path] = None, top_k: int = 5) -> List[Dict]:
        query = self.encoder.encode_item(text=text, image_path=image_path)
        return [
            {"rank": rank, "score": round(score, 6), **metadata}
            for rank, (score, metadata) in enumerate(self.store.search(query, top_k), start=1)
        ]

