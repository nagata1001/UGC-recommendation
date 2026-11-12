from pathlib import Path
import tempfile
import unittest

import numpy as np

from src.encoder import normalize
from src.index_store import FaissStore


class IndexStoreTest(unittest.TestCase):
    def test_cosine_search_returns_nearest_vector(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            vectors = normalize(np.array([[1, 0], [0, 1], [1, 1]], dtype=np.float32))
            metadata = [{"id": "x"}, {"id": "y"}, {"id": "xy"}]
            store = FaissStore(root / "test.faiss", root / "test.jsonl")
            store.build(vectors, metadata)
            store.save()

            loaded = FaissStore(root / "test.faiss", root / "test.jsonl")
            loaded.load()
            results = loaded.search(normalize(np.array([[1, 0]], dtype=np.float32))[0], 2)
            self.assertEqual(results[0][1]["id"], "x")
            self.assertAlmostEqual(results[0][0], 1.0, places=5)


if __name__ == "__main__":
    unittest.main()
