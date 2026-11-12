from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

from .encoder import MultimodalEncoder


def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def batched(values: list, batch_size: int) -> Iterable[list]:
    for start in range(0, len(values), batch_size):
        yield values[start : start + batch_size]


def encode_images_batched(
    encoder: MultimodalEncoder, paths: list[Path], batch_size: int
) -> np.ndarray:
    return np.concatenate(
        [encoder.encode_images(batch) for batch in batched(paths, batch_size)], axis=0
    )


def encode_texts_batched(
    encoder: MultimodalEncoder, texts: list[str], batch_size: int
) -> np.ndarray:
    return np.concatenate(
        [encoder.encode_texts(batch) for batch in batched(texts, batch_size)], axis=0
    )


def recall_at_k(similarity: np.ndarray, ks: tuple[int, ...] = (1, 5, 10)) -> dict:
    order = np.argsort(-similarity, axis=1)
    expected = np.arange(similarity.shape[0])[:, None]
    metrics = {}
    for k in ks:
        cutoff = min(k, similarity.shape[1])
        metrics[f"R@{k}"] = float(np.mean(np.any(order[:, :cutoff] == expected, axis=1)))
    return metrics


def cosine_similarity_matrix(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    """Compute pairwise cosine scores without calling the platform BLAS backend."""
    return np.sum(left[:, None, :] * right[None, :, :], axis=-1, dtype=np.float32)


def evaluate_retrieval(
    records_path: Path,
    batch_size: int = 16,
    device: Optional[str] = None,
) -> dict:
    records = load_jsonl(records_path)
    root = records_path.parent
    texts = [record["text"] for record in records]
    images = [(root / record["image"]).resolve() for record in records]
    encoder = MultimodalEncoder(device=device)
    text_vectors = encode_texts_batched(encoder, texts, batch_size)
    image_vectors = encode_images_batched(encoder, images, batch_size)
    similarity = cosine_similarity_matrix(text_vectors, image_vectors)
    text_to_image = recall_at_k(similarity)
    image_to_text = recall_at_k(similarity.T)
    return {
        "task": "cross_modal_retrieval",
        "dataset": records_path.parent.name,
        "samples": len(records),
        "text_to_image": text_to_image,
        "image_to_text": image_to_text,
        "mean_recall": float(
            np.mean(list(text_to_image.values()) + list(image_to_text.values()))
        ),
    }


def save_report(result: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

