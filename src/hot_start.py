from __future__ import annotations

import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from .cold_start import deterministic_exploration, infer_categories
from .profile_updater import apply_consumer_event
from .tag_backpack import load_jsonl


def _tag_categories(tag: dict) -> set[str]:
    categories = {str(value) for value in tag.get("categories", []) if str(value)}
    return categories or infer_categories(str(tag.get("name", "")))


def category_profile(backpack: dict) -> dict[str, float]:
    positive: dict[str, float] = defaultdict(float)
    negative: dict[str, float] = defaultdict(float)
    for tag in backpack.get("consumer_tag_bag", []):
        signal = (
            0.50 * float(tag.get("long_term_weight", 0.0))
            + 0.30 * float(tag.get("short_term_weight", 0.0))
            + 0.20 * float(tag.get("session_weight", 0.0))
        ) * float(tag.get("confidence", 0.6))
        for category in _tag_categories(tag):
            positive[category] += signal
    for tag in backpack.get("creator_tag_bag", []):
        signal = (
            0.50 * float(tag.get("long_term_weight", 0.0))
            + 0.30 * float(tag.get("short_term_weight", 0.0))
            + 0.20 * float(tag.get("session_weight", 0.0))
        ) * float(tag.get("confidence", 0.6))
        for category in _tag_categories(tag):
            positive[category] += 0.15 * signal
    for tag in backpack.get("negative_tag_bag", []):
        for category in _tag_categories(tag):
            negative[category] += float(tag.get("negative_weight", 0.0))

    maximum = max(positive.values(), default=1.0)
    return {
        category: round(max(0.0, score / maximum - 0.80 * negative.get(category, 0.0)), 6)
        for category, score in positive.items()
    }


def recommend_hot_start(
    backpack: dict,
    candidates: list[dict],
    top_k: int = 5,
    excluded_ids: set[str] | None = None,
) -> list[dict]:
    profile = category_profile(backpack)
    excluded = excluded_ids or set()
    ranked = []
    for item in candidates:
        item_id = str(item["id"])
        if item_id in excluded:
            continue
        categories = sorted(infer_categories(str(item.get("text", ""))))
        affinity = max((profile.get(category, 0.0) for category in categories), default=0.0)
        exploration = deterministic_exploration(str(backpack["user_id"]), item_id)
        quality = float(item.get("quality", 0.70))
        score = 0.80 * affinity + 0.12 * exploration + 0.08 * quality
        ranked.append((score, item, categories, affinity, exploration))
    ranked.sort(key=lambda value: (value[0], str(value[1]["id"])), reverse=True)
    exploration_slots = max(1, round(top_k * 0.20)) if top_k >= 5 else 0
    exploit_count = max(0, top_k - exploration_slots)
    selected = ranked[:exploit_count]
    selected_ids = {str(value[1]["id"]) for value in selected}
    exploration_pool = [
        value for value in ranked
        if str(value[1]["id"]) not in selected_ids and value[3] < 0.25
    ]
    exploration_pool.sort(key=lambda value: value[4], reverse=True)
    selected.extend(exploration_pool[:exploration_slots])
    if len(selected) < top_k:
        selected_ids = {str(value[1]["id"]) for value in selected}
        selected.extend(
            value for value in ranked
            if str(value[1]["id"]) not in selected_ids
        )
    selected = selected[:top_k]
    return [
        {
            "rank": rank,
            "ugc_id": item["id"],
            "text": item.get("text", ""),
            "image": item.get("image", ""),
            "categories": categories,
            "score": round(score, 6),
            "score_detail": {
                "dynamic_interest": round(affinity, 6),
                "exploration": round(exploration, 6),
                "quality": round(float(item.get("quality", 0.70)), 6),
            },
        }
        for rank, (score, item, categories, affinity, exploration) in enumerate(selected, start=1)
    ]


def _latent_preferences(backpack: dict, day: int) -> dict[str, float]:
    values: dict[str, float] = defaultdict(float)
    for tag in backpack.get("consumer_tag_bag", []):
        if float(tag.get("sources", {}).get("registration_selection", 0.0)) <= 0:
            continue
        for category in _tag_categories(tag):
            values[category] = max(values[category], float(tag.get("long_term_weight", 0.0)))
    # Scripted preference shifts make adaptation measurable rather than circular.
    if backpack["user_id"] == "user-001" and day >= 4:
        values["旅行户外"] = 0.35
        values["体育运动"] = 0.25
        values["科技数码"] = 1.00
    if backpack["user_id"] == "user-004" and day >= 5:
        values["交通工具"] = 0.45
        values["旅行户外"] = 0.90
    maximum = max(values.values(), default=1.0)
    return {key: value / maximum for key, value in values.items()}


def _event_type(interest: float, rng: random.Random) -> str:
    value = rng.random()
    if interest >= 0.75:
        if value < 0.20:
            return "save"
        if value < 0.40:
            return "like"
        if value < 0.65:
            return "complete"
        if value < 0.90:
            return "dwell"
        return "click"
    if interest >= 0.40:
        if value < 0.35:
            return "click"
        if value < 0.65:
            return "dwell"
        if value < 0.82:
            return "quick_skip"
        return "impression"
    if value < 0.20:
        return "not_interested"
    if value < 0.55:
        return "quick_skip"
    return "impression"


def _ranking_metrics(recommendations: list[dict], latent: dict[str, float], k: int = 5) -> dict:
    gains = [
        max((latent.get(category, 0.0) for category in item["categories"]), default=0.0)
        for item in recommendations[:k]
    ]
    binary = [gain >= 0.50 for gain in gains]
    dcg = sum((1.0 if relevant else 0.0) / math.log2(index + 2) for index, relevant in enumerate(binary))
    ideal_count = min(k, len(recommendations)) if any(value >= 0.50 for value in latent.values()) else 0
    idcg = sum(1.0 / math.log2(index + 2) for index in range(ideal_count))
    return {
        "hit_rate_at_5": 1.0 if any(binary) else 0.0,
        "precision_at_5": round(sum(binary) / max(1, min(k, len(recommendations))), 6),
        "ndcg_at_5": round(dcg / idcg if idcg else 0.0, 6),
    }


def _top_profile(profile: dict[str, float], limit: int = 5) -> list[dict]:
    return [
        {"category": category, "weight": weight}
        for category, weight in sorted(profile.items(), key=lambda value: value[1], reverse=True)[:limit]
    ]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def simulate_seven_days(
    backpacks_path: Path,
    candidates_path: Path,
    final_backpacks_path: Path,
    events_path: Path,
    report_path: Path,
    days: int = 7,
    exposures_per_user: int = 10,
    seed: int = 20261111,
) -> dict:
    backpacks = {row["user_id"]: row for row in load_jsonl(backpacks_path)}
    candidates = load_jsonl(candidates_path)
    rng = random.Random(seed)
    start_time = datetime.fromisoformat("2026-11-12T09:00:00+08:00")
    last_seen_day: dict[str, dict[str, int]] = {user_id: {} for user_id in backpacks}
    events: list[dict] = []
    daily_results: list[dict] = []

    for day in range(1, days + 1):
        user_results = []
        daily_event_counts: Counter[str] = Counter()
        for user_id, backpack in backpacks.items():
            latent = _latent_preferences(backpack, day)
            cooldown_ids = {
                item_id for item_id, seen_day in last_seen_day[user_id].items()
                if day - seen_day <= 2
            }
            before = recommend_hot_start(backpack, candidates, exposures_per_user, cooldown_ids)
            before_metrics = _ranking_metrics(before, latent)
            applied = []
            for position, recommendation in enumerate(before, start=1):
                interest = max(
                    (latent.get(category, 0.0) for category in recommendation["categories"]),
                    default=0.0,
                )
                event_type = _event_type(interest, rng)
                event_time = start_time + timedelta(days=day - 1, minutes=position * 3)
                event = {
                    "event_id": f"hot:{day}:{user_id}:{recommendation['ugc_id']}",
                    "user_id": user_id,
                    "ugc_id": recommendation["ugc_id"],
                    "event_type": event_type,
                    "event_time": event_time.isoformat(),
                    "position": position,
                    "text": recommendation["text"],
                    "tags": [
                        {"name": category, "confidence": 0.90, "source": "ugc_text_rule"}
                        for category in recommendation["categories"]
                    ],
                    "simulated_interest": round(interest, 6),
                }
                backpack, update = apply_consumer_event(backpack, event)
                event["update_status"] = update["status"]
                event["tag_updates"] = update["tag_updates"]
                events.append(event)
                applied.append(event)
                daily_event_counts[event_type] += 1
                last_seen_day[user_id][str(recommendation["ugc_id"])] = day
            backpacks[user_id] = backpack
            after_cooldown_ids = {
                item_id for item_id, seen_day in last_seen_day[user_id].items()
                if day - seen_day <= 2
            }
            after = recommend_hot_start(backpack, candidates, 5, after_cooldown_ids)
            user_results.append(
                {
                    "user_id": user_id,
                    "latent_preferences": latent,
                    "metrics_before_update": before_metrics,
                    "recommendations_before_update": before[:5],
                    "events": [
                        {
                            "ugc_id": event["ugc_id"],
                            "event_type": event["event_type"],
                            "categories": [tag["name"] for tag in event["tags"]],
                        }
                        for event in applied
                    ],
                    "profile_after_update": _top_profile(category_profile(backpack)),
                    "recommendations_after_update": after,
                }
            )
        daily_results.append(
            {
                "day": day,
                "date": (start_time + timedelta(days=day - 1)).date().isoformat(),
                "event_counts": dict(sorted(daily_event_counts.items())),
                "mean_hit_rate_at_5": round(
                    sum(user["metrics_before_update"]["hit_rate_at_5"] for user in user_results)
                    / len(user_results),
                    6,
                ),
                "mean_precision_at_5": round(
                    sum(user["metrics_before_update"]["precision_at_5"] for user in user_results)
                    / len(user_results),
                    6,
                ),
                "mean_ndcg_at_5": round(
                    sum(user["metrics_before_update"]["ndcg_at_5"] for user in user_results)
                    / len(user_results),
                    6,
                ),
                "users": user_results,
            }
        )

    final_rows = [backpacks[user_id] for user_id in sorted(backpacks)]
    write_jsonl(final_backpacks_path, final_rows)
    write_jsonl(events_path, events)
    report = {
        "task": "seven_day_hot_start_behavior_replay",
        "seed": seed,
        "days": days,
        "users": len(backpacks),
        "candidates": len(candidates),
        "exposures_per_user_per_day": exposures_per_user,
        "total_events": len(events),
        "event_counts": dict(sorted(Counter(event["event_type"] for event in events).items())),
        "ranking_policy": {
            "dynamic_interest": 0.80,
            "exploration": 0.12,
            "quality": 0.08,
            "creator_signal_multiplier": 0.15,
            "negative_signal_multiplier": 0.80,
        },
        "daily_results": daily_results,
        "final_users": [
            {
                "user_id": row["user_id"],
                "stage": row["stage"],
                "effective_behavior_count": row["profile_state"]["effective_behavior_count"],
                "behavior_profile_weight": row["profile_state"]["behavior_profile_weight"],
                "top_profile": _top_profile(category_profile(row)),
                "final_recommendations": recommend_hot_start(
                    row,
                    candidates,
                    5,
                    {
                        item_id for item_id, seen_day in last_seen_day[row["user_id"]].items()
                        if days - seen_day <= 2
                    },
                ),
            }
            for row in final_rows
        ],
        "notes": [
            "行为按时间顺序回放，推荐只能使用当前事件之前的画像。",
            "user-001从第4天转向科技数码，user-004从第5天增强旅行户外兴趣，用于测试兴趣漂移。",
            "标签来自候选UGC文本关键词规则；本实验验证热启动更新链路，不代表线上真实CTR。",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
