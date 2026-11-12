from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw


def create_demo_data(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    examples = [
        ("post-red", "公园里的红色圆形艺术装置", "red_circle.png", "circle", "#d9363e"),
        ("post-blue", "蓝色方形科技界面", "blue_square.png", "square", "#2878c8"),
        ("post-green", "自然植物与绿色叶片", "green_leaf.png", "leaf", "#3c9d58"),
    ]
    rows = []
    for item_id, text, filename, shape, color in examples:
        image = Image.new("RGB", (512, 384), "white")
        draw = ImageDraw.Draw(image)
        if shape == "circle":
            draw.ellipse((130, 65, 380, 315), fill=color)
        elif shape == "square":
            draw.rounded_rectangle((125, 65, 385, 325), radius=24, fill=color)
        else:
            draw.ellipse((105, 95, 335, 270), fill=color)
            draw.line((325, 260, 405, 330), fill="#246c38", width=18)
        image.save(output_dir / filename)
        rows.append({"id": item_id, "text": text, "image": filename})

    dataset_path = output_dir / "ugc.jsonl"
    with dataset_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return dataset_path

