from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

import numpy as np
from PIL import Image
import torch
from transformers import ChineseCLIPModel, ChineseCLIPProcessor

from .config import MODEL_DIR, MODEL_ID


def normalize(vectors: np.ndarray) -> np.ndarray:
    vectors = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return vectors / np.clip(norms, 1e-12, None)


class MultimodalEncoder:
    def __init__(self, device: Optional[str] = None) -> None:
        model_source = str(MODEL_DIR) if (MODEL_DIR / "config.json").exists() else MODEL_ID
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.processor = ChineseCLIPProcessor.from_pretrained(model_source)
        self.model = ChineseCLIPModel.from_pretrained(model_source)
        self.model.to(self.device)
        self.model.eval()

    @property
    def dimension(self) -> int:
        return int(self.model.config.projection_dim)

    def encode_texts(self, texts: Iterable[str]) -> np.ndarray:
        values = [str(text).strip() for text in texts]
        if not values:
            return np.empty((0, self.dimension), dtype=np.float32)
        max_length = int(self.model.config.text_config.max_position_embeddings)
        inputs = self.processor(
            text=values,
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="pt",
        )
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with torch.inference_mode():
            vectors = self.model.get_text_features(**inputs)
        return normalize(vectors.detach().cpu().float().numpy())

    def encode_images(self, image_paths: Iterable[Path]) -> np.ndarray:
        images = []
        for image_path in image_paths:
            with Image.open(image_path) as image:
                images.append(image.convert("RGB"))
        if not images:
            return np.empty((0, self.dimension), dtype=np.float32)
        inputs = self.processor(images=images, return_tensors="pt")
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with torch.inference_mode():
            vectors = self.model.get_image_features(**inputs)
        return normalize(vectors.detach().cpu().float().numpy())

    def encode_item(self, text: str = "", image_path: Optional[Path] = None) -> np.ndarray:
        parts = []
        if text.strip():
            parts.append(self.encode_texts([text])[0])
        if image_path is not None:
            parts.append(self.encode_images([image_path])[0])
        if not parts:
            raise ValueError("文本和图片至少需要提供一个")
        return normalize(np.mean(np.stack(parts), axis=0, keepdims=True))[0]

