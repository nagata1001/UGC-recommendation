from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import faiss
import numpy as np


class FaissStore:
    def __init__(self, index_path: Path, metadata_path: Path) -> None:
        self.index_path = index_path
        self.metadata_path = metadata_path
        self.index = None
        self.metadata: List[Dict] = []

    def build(self, vectors: np.ndarray, metadata: Sequence[Dict]) -> None:
        matrix = np.ascontiguousarray(vectors, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[0] != len(metadata):
            raise ValueError("向量数量与元数据数量不一致")
        self.index = faiss.IndexFlatIP(matrix.shape[1])
        self.index.add(matrix)
        self.metadata = list(metadata)

    def save(self) -> None:
        if self.index is None:
            raise RuntimeError("索引尚未建立")
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_path))
        with self.metadata_path.open("w", encoding="utf-8") as handle:
            for row in self.metadata:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def load(self) -> None:
        self.index = faiss.read_index(str(self.index_path))
        with self.metadata_path.open("r", encoding="utf-8") as handle:
            self.metadata = [json.loads(line) for line in handle if line.strip()]
        if self.index.ntotal != len(self.metadata):
            raise RuntimeError("索引与元数据数量不一致，请重新建库")

    def search(self, query: np.ndarray, top_k: int) -> List[Tuple[float, Dict]]:
        if self.index is None:
            raise RuntimeError("索引尚未加载")
        query = np.ascontiguousarray(query.reshape(1, -1), dtype=np.float32)
        count = min(max(1, top_k), self.index.ntotal)
        scores, indices = self.index.search(query, count)
        return [
            (float(score), self.metadata[int(index)])
            for score, index in zip(scores[0], indices[0])
            if index >= 0
        ]

