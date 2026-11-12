from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .cold_start import infer_categories


SCHEMA_VERSION = 1
REGISTRATION_CONFIDENCE = 0.60


def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _selected_interests(profile: dict) -> list[tuple[str, float]]:
    interests: list[tuple[str, float]] = []
    for value in profile.get("selected_interests", []):
        if isinstance(value, str):
            name, weight = value.strip(), 1.0
        else:
            name = str(value.get("name", "")).strip()
            weight = float(value.get("weight", 1.0))
        if name and weight > 0:
            interests.append((name, weight))
    return interests


def build_initial_tag_backpack(profile: dict, generated_at: str) -> dict:
    interests = _selected_interests(profile)
    max_weight = max((weight for _, weight in interests), default=1.0)
    consumer_tags = []
    for name, raw_weight in interests:
        normalized_weight = raw_weight / max_weight
        consumer_tags.append(
            {
                "tag_id": f"selected_interest:{name}",
                "name": name,
                "categories": sorted(infer_categories(name)),
                "long_term_weight": round(normalized_weight, 6),
                "short_term_weight": 0.0,
                "session_weight": 0.0,
                "negative_weight": 0.0,
                "confidence": REGISTRATION_CONFIDENCE,
                "evidence_count": 1,
                "sources": {
                    "registration_selection": round(raw_weight, 6),
                    "behavior": 0.0,
                    "published_post": 0.0,
                },
                "last_event": "registration_selection",
                "updated_at": generated_at,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "user_id": profile["user_id"],
        "stage": "cold_start",
        "demographic_context": {
            "age": profile.get("age"),
            "gender": profile.get("gender"),
            "region": profile.get("region"),
            "ranking_policy": {
                "age_direct_ranking": False,
                "gender_direct_ranking": False,
                "region_context_only": True,
            },
        },
        "consumer_tag_bag": consumer_tags,
        "creator_tag_bag": [],
        "negative_tag_bag": [],
        "profile_state": {
            "effective_behavior_count": 0,
            "published_post_count": 0,
            "cold_start_prior_weight": 1.0,
            "behavior_profile_weight": 0.0,
            "last_updated_at": generated_at,
        },
    }


def create_initial_tag_backpacks(
    users_path: Path,
    output_path: Path,
    generated_at: str | None = None,
) -> list[dict]:
    timestamp = generated_at or datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    profiles = load_jsonl(users_path)
    backpacks = [build_initial_tag_backpack(profile, timestamp) for profile in profiles]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for backpack in backpacks:
            handle.write(json.dumps(backpack, ensure_ascii=False) + "\n")
    return backpacks
