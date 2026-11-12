import unittest

import numpy as np

from src.evaluator import cosine_similarity_matrix, recall_at_k


class RetrievalMetricsTest(unittest.TestCase):
    def test_cosine_similarity_matrix(self) -> None:
        left = np.array([[1, 0], [0, 1]], dtype=np.float32)
        right = np.array([[1, 0], [1, 1]], dtype=np.float32)
        scores = cosine_similarity_matrix(left, right)
        np.testing.assert_allclose(scores, np.array([[1, 1], [0, 1]], dtype=np.float32))

    def test_perfect_retrieval(self) -> None:
        metrics = recall_at_k(np.eye(3, dtype=np.float32))
        self.assertEqual(metrics["R@1"], 1.0)
        self.assertEqual(metrics["R@5"], 1.0)

    def test_partial_retrieval(self) -> None:
        similarity = np.array([[0.1, 0.9], [0.2, 0.8]], dtype=np.float32)
        metrics = recall_at_k(similarity, ks=(1, 2))
        self.assertEqual(metrics["R@1"], 0.5)
        self.assertEqual(metrics["R@2"], 1.0)


if __name__ == "__main__":
    unittest.main()

