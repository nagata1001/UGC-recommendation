from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.tag_backpack import create_initial_tag_backpacks


def main() -> None:
    parser = argparse.ArgumentParser(description="从初始用户画像生成冷启动标签背包")
    parser.add_argument(
        "--users",
        type=Path,
        default=ROOT / "data" / "cold_start" / "users.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "user_profiles" / "initial_tag_backpacks.jsonl",
    )
    args = parser.parse_args()
    backpacks = create_initial_tag_backpacks(args.users.resolve(), args.output.resolve())
    print(f"已生成 {len(backpacks)} 个用户标签背包：{args.output.resolve()}")


if __name__ == "__main__":
    main()
