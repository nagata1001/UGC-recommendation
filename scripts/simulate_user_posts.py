from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.profile_updater import apply_publish_event, infer_post_tags
from src.tag_backpack import load_jsonl


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_simulated_posts(recommendation_report: Path, candidate_root: Path) -> list[dict]:
    report = json.loads(recommendation_report.read_text(encoding="utf-8"))
    start = datetime.fromisoformat("2026-11-11T09:00:00+08:00")
    posts = []
    sequence = 0
    for user in report["results"]:
        for local_index, recommendation in enumerate(user["recommendations"][:2], start=1):
            sequence += 1
            event_time = start + timedelta(minutes=sequence * 35)
            relative_image = Path("..") / "eval" / "coco_cn_mini_100" / recommendation["image"]
            post = {
                "event_id": f"publish:{user['user_id']}:{local_index}",
                "post_id": f"sim-post-{user['user_id']}-{local_index:02d}",
                "user_id": user["user_id"],
                "event_type": "publish",
                "event_time": event_time.isoformat(timespec="seconds"),
                "text": f"我的图文分享：{recommendation['text']}",
                "image": str(relative_image),
                "source_ugc_id": recommendation["ugc_id"],
            }
            post["tags"] = infer_post_tags(post)
            posts.append(post)
    return posts


def main() -> None:
    parser = argparse.ArgumentParser(description="模拟用户发布图文UGC并更新创作标签背包")
    parser.add_argument(
        "--backpacks",
        type=Path,
        default=ROOT / "data" / "user_profiles" / "initial_tag_backpacks.jsonl",
    )
    parser.add_argument(
        "--recommendations",
        type=Path,
        default=ROOT / "reports" / "cold_start_recommendations.json",
    )
    parser.add_argument(
        "--posts-output",
        type=Path,
        default=ROOT / "data" / "simulation" / "user_posts.jsonl",
    )
    parser.add_argument(
        "--backpacks-output",
        type=Path,
        default=ROOT / "data" / "user_profiles" / "tag_backpacks_after_posts.jsonl",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=ROOT / "reports" / "user_post_simulation.json",
    )
    args = parser.parse_args()

    backpacks = {row["user_id"]: row for row in load_jsonl(args.backpacks.resolve())}
    posts = build_simulated_posts(args.recommendations.resolve(), args.posts_output.resolve().parent)
    updates = []
    for post in posts:
        user_id = post["user_id"]
        backpacks[user_id], event_result = apply_publish_event(backpacks[user_id], post)
        updates.append({"user_id": user_id, **event_result})

    ordered = [backpacks[user_id] for user_id in sorted(backpacks)]
    write_jsonl(args.posts_output.resolve(), posts)
    write_jsonl(args.backpacks_output.resolve(), ordered)
    report = {
        "task": "simulated_user_posts_and_creator_profile_update",
        "users": len(ordered),
        "posts": len(posts),
        "applied_events": sum(update["status"] == "applied" for update in updates),
        "update_policy": {
            "publish_strength": 0.40,
            "tag_confidence": 0.90,
            "repeat_decay": "0.7 ^ previous_evidence_count",
            "long_term_multiplier": 0.60,
            "short_term_multiplier": 1.00,
            "session_multiplier": 1.00,
        },
        "events": updates,
        "users_after_update": [
            {
                "user_id": bag["user_id"],
                "published_post_count": bag["profile_state"]["published_post_count"],
                "creator_stage": bag["profile_state"]["creator_stage"],
                "creator_tag_bag": bag["creator_tag_bag"],
            }
            for bag in ordered
        ],
    }
    args.report_output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.report_output.resolve().write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"模拟用户：{len(ordered)}")
    print(f"模拟发帖：{len(posts)}")
    print(f"更新后背包：{args.backpacks_output.resolve()}")
    print(f"更新报告：{args.report_output.resolve()}")


if __name__ == "__main__":
    main()
