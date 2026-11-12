from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import tarfile

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SOURCE_DIR = DATA_DIR / "sources"
EVAL_DIR = DATA_DIR / "eval"

COCO_CN_ARCHIVE = SOURCE_DIR / "coco-cn" / "coco-cn-version1805v1.1.tar.gz"
COCO_CN_EXTRACTED = SOURCE_DIR / "coco-cn" / "coco-cn-version1805v1.1"
COCO_CN_URL = (
    "https://hf-mirror.com/datasets/AIMClab-RUC/COCO-CN/resolve/main/"
    "coco-cn-version1805v1.1.tar.gz"
)


def download_with_curl(url: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.stat().st_size > 0:
        return
    temporary = output.with_suffix(output.suffix + ".part")
    subprocess.run(
        [
            "curl.exe",
            "-L",
            "--fail",
            "--retry",
            "3",
            "--silent",
            "--show-error",
            url,
            "-o",
            str(temporary),
        ],
        check=True,
    )
    temporary.replace(output)


def download_and_verify_image(url: str, output: Path) -> None:
    if output.exists():
        try:
            with Image.open(output) as image:
                image.load()
            return
        except Exception:
            output.unlink()
    download_with_curl(url, output)
    with Image.open(output) as image:
        image.load()


def evenly_spaced(values: list[str], count: int) -> list[str]:
    if count >= len(values):
        return values
    indices = np.linspace(0, len(values) - 1, num=count, dtype=int)
    return [values[int(index)] for index in indices]


def prepare_coco_cn(count: int) -> Path:
    download_with_curl(COCO_CN_URL, COCO_CN_ARCHIVE)
    if not COCO_CN_EXTRACTED.exists():
        with tarfile.open(COCO_CN_ARCHIVE, "r:gz") as archive:
            archive.extractall(COCO_CN_ARCHIVE.parent, filter="data")

    test_ids = [
        line.strip()
        for line in (COCO_CN_EXTRACTED / "coco-cn_test.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    captions: dict[str, list[str]] = {}
    caption_path = COCO_CN_EXTRACTED / "imageid.human-written-caption.txt"
    for line in caption_path.read_text(encoding="utf-8").splitlines():
        key, text = line.split("\t", 1)
        captions.setdefault(key.split("#", 1)[0], []).append(text.strip())

    selected = evenly_spaced([image_id for image_id in test_ids if image_id in captions], count)
    output_dir = EVAL_DIR / f"coco_cn_mini_{len(selected)}"
    image_dir = output_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    download_jobs = []
    records = []
    for image_id in selected:
        split = image_id.split("_", 2)[1]
        image_path = image_dir / f"{image_id}.jpg"
        url = f"http://images.cocodataset.org/{split}/{image_id}.jpg"
        download_jobs.append((url, image_path))
        records.append(
            {
                "id": image_id,
                "text": captions[image_id][0],
                "image": str(image_path.relative_to(output_dir)),
                "source_url": url,
            }
        )
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda job: download_and_verify_image(*job), download_jobs))
    records_path = output_dir / "records.jsonl"
    with records_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return records_path


def main() -> None:
    parser = argparse.ArgumentParser(description="下载并准备小型开源评测数据")
    parser.add_argument("--dataset", choices=["coco-cn"], default="coco-cn")
    parser.add_argument("--coco-count", type=int, default=100)
    args = parser.parse_args()

    print(f"COCO-CN: {prepare_coco_cn(args.coco_count)}")


if __name__ == "__main__":
    main()

