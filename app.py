from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import sys

from src.config import CACHE_DIR, DATA_DIR, INDEX_DIR, MODEL_DIR, MODEL_ID, ROOT


def command_doctor(_: argparse.Namespace) -> None:
    packages = ["torch", "transformers", "huggingface-hub", "faiss-cpu", "paddlepaddle", "paddleocr"]
    print(f"Python: {sys.version.split()[0]}")
    print(f"Platform: {platform.platform()}")
    print(f"Project: {ROOT}")
    print(f"Model: {MODEL_DIR}")
    print(f"Cache: {CACHE_DIR}")
    print(f"Index: {INDEX_DIR}")
    for package in packages:
        try:
            version = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            if package == "faiss-cpu":
                try:
                    import faiss

                    version = getattr(faiss, "__version__", "installed by conda")
                except ImportError:
                    version = "NOT INSTALLED"
            else:
                version = "NOT INSTALLED"
        print(f"{package}: {version}")


def command_download(args: argparse.Namespace) -> None:
    from huggingface_hub import snapshot_download

    print(f"下载 {MODEL_ID} 到 {MODEL_DIR}")
    snapshot_download(
        repo_id=MODEL_ID,
        local_dir=str(MODEL_DIR),
        ignore_patterns=["clip_cn_*.pt"],
    )
    print("Chinese-CLIP 下载完成")
    if not args.skip_ocr:
        from src.ocr import OCRExtractor

        print("初始化 PaddleOCR 移动模型")
        OCRExtractor()
        print("PaddleOCR 模型准备完成")


def command_demo_data(_: argparse.Namespace) -> None:
    from src.demo_data import create_demo_data

    output = create_demo_data(DATA_DIR / "demo")
    print(f"示例数据已生成：{output}")


def command_build(args: argparse.Namespace) -> None:
    from src.indexer import build_index

    count = build_index(args.input.resolve(), use_ocr=args.ocr, device=args.device)
    print(f"索引建立完成，共 {count} 条 UGC")


def command_search(args: argparse.Namespace) -> None:
    from src.searcher import Searcher

    if not args.text and args.image is None:
        raise SystemExit("--text 和 --image 至少提供一个")
    image_path = args.image.resolve() if args.image else None
    results = Searcher(device=args.device).search(args.text or "", image_path, args.top_k)
    print(json.dumps(results, ensure_ascii=False, indent=2))


def command_evaluate(args: argparse.Namespace) -> None:
    from src.evaluator import evaluate_retrieval, save_report

    result = evaluate_retrieval(args.input.resolve(), args.batch_size, args.device)
    output = args.output.resolve()
    save_report(result, output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"评测报告：{output}")


def command_cold_start(args: argparse.Namespace) -> None:
    from src.cold_start import recommend_cold_start, save_recommendations

    result = recommend_cold_start(
        args.users.resolve(),
        args.candidates.resolve(),
        top_k=args.top_k,
        batch_size=args.batch_size,
        device=args.device,
    )
    output = args.output.resolve()
    save_recommendations(result, output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"冷启动推荐报告：{output}")


def command_tag_backpacks(args: argparse.Namespace) -> None:
    from src.tag_backpack import create_initial_tag_backpacks

    output = args.output.resolve()
    backpacks = create_initial_tag_backpacks(args.users.resolve(), output)
    print(f"已生成 {len(backpacks)} 个用户标签背包：{output}")


def command_hot_start_sim(args: argparse.Namespace) -> None:
    from src.hot_start import simulate_seven_days

    result = simulate_seven_days(
        args.backpacks.resolve(),
        args.candidates.resolve(),
        args.final_backpacks.resolve(),
        args.events.resolve(),
        args.output.resolve(),
        days=args.days,
        exposures_per_user=args.exposures,
        seed=args.seed,
    )
    print(json.dumps({key: result[key] for key in ("task", "days", "users", "total_events", "event_counts")}, ensure_ascii=False, indent=2))
    print(f"热启动实验报告：{args.output.resolve()}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="多模态 UGC 最小本地测试系统")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="检查环境与项目路径")
    doctor.set_defaults(func=command_doctor)

    download = subparsers.add_parser("download", help="下载模型到项目目录")
    download.add_argument("--skip-ocr", action="store_true", help="暂不下载 OCR 模型")
    download.set_defaults(func=command_download)

    demo = subparsers.add_parser("demo-data", help="生成三条图文示例 UGC")
    demo.set_defaults(func=command_demo_data)

    build = subparsers.add_parser("build", help="从 JSONL 建立 FAISS 索引")
    build.add_argument("--input", type=Path, required=True)
    build.add_argument("--ocr", action="store_true", help="提取图片文字并合并到文本")
    build.add_argument("--device", choices=["cpu", "cuda"], default=None)
    build.set_defaults(func=command_build)

    search = subparsers.add_parser("search", help="使用文本或图片搜索")
    search.add_argument("--text", default="")
    search.add_argument("--image", type=Path)
    search.add_argument("--top-k", type=int, default=5)
    search.add_argument("--device", choices=["cpu", "cuda"], default=None)
    search.set_defaults(func=command_search)

    evaluate = subparsers.add_parser("evaluate", help="评估跨模态图文检索")
    evaluate.add_argument("--input", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--batch-size", type=int, default=16)
    evaluate.add_argument("--device", choices=["cpu", "cuda"], default=None)
    evaluate.set_defaults(func=command_evaluate)

    cold_start = subparsers.add_parser("cold-start", help="根据初始用户画像生成冷启动推荐")
    cold_start.add_argument("--users", type=Path, required=True, help="模拟用户画像 JSONL")
    cold_start.add_argument("--candidates", type=Path, required=True, help="候选 UGC JSONL")
    cold_start.add_argument("--output", type=Path, required=True, help="推荐结果 JSON")
    cold_start.add_argument("--top-k", type=int, default=5)
    cold_start.add_argument("--batch-size", type=int, default=16)
    cold_start.add_argument("--device", choices=["cpu", "cuda"], default=None)
    cold_start.set_defaults(func=command_cold_start)

    tag_backpacks = subparsers.add_parser("tag-backpacks", help="从初始画像生成用户标签背包")
    tag_backpacks.add_argument("--users", type=Path, required=True, help="初始用户画像 JSONL")
    tag_backpacks.add_argument("--output", type=Path, required=True, help="标签背包输出 JSONL")
    tag_backpacks.set_defaults(func=command_tag_backpacks)

    hot_start = subparsers.add_parser("hot-start-sim", help="按时间顺序模拟用户行为并动态更新推荐")
    hot_start.add_argument("--backpacks", type=Path, required=True, help="初始或发帖后的标签背包 JSONL")
    hot_start.add_argument("--candidates", type=Path, required=True, help="候选 UGC JSONL")
    hot_start.add_argument("--final-backpacks", type=Path, required=True, help="最终标签背包 JSONL")
    hot_start.add_argument("--events", type=Path, required=True, help="行为事件明细 JSONL")
    hot_start.add_argument("--output", type=Path, required=True, help="七天实验报告 JSON")
    hot_start.add_argument("--days", type=int, default=7)
    hot_start.add_argument("--exposures", type=int, default=10, help="每位用户每天的模拟曝光数")
    hot_start.add_argument("--seed", type=int, default=20261111)
    hot_start.set_defaults(func=command_hot_start_sim)
    return parser


if __name__ == "__main__":
    arguments = build_parser().parse_args()
    arguments.func(arguments)

