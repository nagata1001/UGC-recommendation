from __future__ import annotations

import copy
import math
from datetime import datetime

import numpy as np

from .cold_start import infer_categories


PUBLISH_STRENGTH = 0.40
CREATOR_DECAY_DAYS = {
    "long_term_weight": 120.0,
    "short_term_weight": 14.0,
    "session_weight": 0.25,
}

BEHAVIOR_STRENGTH = {
    "impression": 0.0,
    "click": 0.05,
    "dwell": 0.10,
    "complete": 0.15,
    "like": 0.20,
    "save": 0.30,
    "share": 0.30,
    "follow_after_click": 0.35,
    "quick_skip": -0.05,
    "not_interested": -0.40,
}

CONSUMER_DECAY_DAYS = {
    "long_term_weight": 120.0,
    "short_term_weight": 14.0,
    "session_weight": 0.25,
}


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def infer_post_tags(post: dict) -> list[dict]:
    categories = sorted(infer_categories(str(post.get("text", ""))))
    return [
        {
            "name": category,
            "confidence": 0.90,
            "source": "post_text_rule",
        }
        for category in categories
    ]


def _decay(value: float, previous_time: str, event_time: str, tau_days: float) -> float:
    elapsed = max(0.0, (parse_time(event_time) - parse_time(previous_time)).total_seconds())
    elapsed_days = elapsed / 86400.0
    return float(value) * math.exp(-elapsed_days / tau_days)


def _find_tag(tags: list[dict], name: str) -> dict | None:
    return next((tag for tag in tags if tag["name"] == name), None)


def _new_tag(name: str, event_time: str, prefix: str, confidence: float) -> dict:
    return {
        "tag_id": f"{prefix}:{name}",
        "name": name,
        "categories": [name],
        "long_term_weight": 0.0,
        "short_term_weight": 0.0,
        "session_weight": 0.0,
        "negative_weight": 0.0,
        "confidence": confidence,
        "evidence_count": 0,
        "behavior_evidence_count": 0,
        "sources": {
            "registration_selection": 0.0,
            "behavior": 0.0,
            "published_post": 0.0,
        },
        "last_event": "",
        "updated_at": event_time,
    }


def apply_consumer_event(backpack: dict, event: dict) -> tuple[dict, dict]:
    """Apply one exposure/consumption event without changing the creator tag bag."""
    updated = copy.deepcopy(backpack)
    state = updated.setdefault("profile_state", {})
    event_id = str(event["event_id"])
    processed = state.setdefault("processed_event_ids", [])
    if event_id in processed:
        return updated, {"event_id": event_id, "status": "duplicate_skipped", "tag_updates": []}

    event_type = str(event["event_type"])
    if event_type not in BEHAVIOR_STRENGTH:
        raise ValueError(f"不支持的消费行为：{event_type}")
    event_time = str(event["event_time"])
    strength = BEHAVIOR_STRENGTH[event_type]
    inferred_tags = event.get("tags") or [
        {"name": category, "confidence": 0.90, "source": "ugc_text_rule"}
        for category in sorted(infer_categories(str(event.get("text", ""))))
    ]

    tag_updates = []
    if strength != 0.0:
        target_name = "consumer_tag_bag" if strength > 0 else "negative_tag_bag"
        target = updated.setdefault(target_name, [])
        for inferred in inferred_tags:
            name = str(inferred["name"])
            confidence = float(np.clip(inferred.get("confidence", 0.0), 0.0, 1.0))
            tag = _find_tag(target, name)
            if tag is None:
                tag = _new_tag(name, event_time, "behavior" if strength > 0 else "negative", confidence)
                target.append(tag)

            for key in ("long_term_weight", "short_term_weight", "session_weight", "negative_weight"):
                tag.setdefault(key, 0.0)
            tag.setdefault("categories", [name])
            tag.setdefault("confidence", confidence)
            tag.setdefault("evidence_count", 0)
            tag.setdefault("behavior_evidence_count", 0)
            tag.setdefault("sources", {}).setdefault("behavior", 0.0)
            previous_time = str(tag.get("updated_at", state.get("last_updated_at", event_time)))
            behavior_count = int(tag.get("behavior_evidence_count", 0))
            repeat_decay = 0.85 ** min(behavior_count, 8)
            delta = abs(strength) * confidence * repeat_decay
            before = {
                key: float(tag.get(key, 0.0))
                for key in ("long_term_weight", "short_term_weight", "session_weight", "negative_weight")
            }

            if strength > 0:
                multipliers = {
                    "long_term_weight": 0.40,
                    "short_term_weight": 0.80,
                    "session_weight": 1.00,
                }
                for key, multiplier in multipliers.items():
                    decayed = _decay(before[key], previous_time, event_time, CONSUMER_DECAY_DAYS[key])
                    tag[key] = round(float(np.clip(decayed + delta * multiplier, 0.0, 1.0)), 6)
            else:
                decayed = _decay(before["negative_weight"], previous_time, event_time, 30.0)
                tag["negative_weight"] = round(float(np.clip(decayed + delta, 0.0, 1.0)), 6)

            evidence_count = int(tag.get("evidence_count", 0))
            tag["confidence"] = round(
                (float(tag["confidence"]) * evidence_count + confidence) / (evidence_count + 1), 6
            )
            tag["evidence_count"] = evidence_count + 1
            tag["behavior_evidence_count"] = behavior_count + 1
            tag["sources"]["behavior"] = round(float(tag["sources"]["behavior"]) + delta, 6)
            tag["last_event"] = event_type
            tag["updated_at"] = event_time
            tag_updates.append(
                {
                    "tag": name,
                    "target": target_name,
                    "delta": round(delta, 6),
                    "before": before,
                    "after": {
                        key: tag[key]
                        for key in ("long_term_weight", "short_term_weight", "session_weight", "negative_weight")
                    },
                }
            )

        target.sort(
            key=lambda value: max(
                float(value.get("long_term_weight", 0.0)),
                float(value.get("negative_weight", 0.0)),
            ),
            reverse=True,
        )
        state["effective_behavior_count"] = int(state.get("effective_behavior_count", 0)) + 1

    effective_count = int(state.get("effective_behavior_count", 0))
    state["behavior_profile_weight"] = round(min(0.95, effective_count / 20.0), 6)
    state["cold_start_prior_weight"] = round(1.0 - state["behavior_profile_weight"], 6)
    state["consumer_stage"] = "hot_start" if effective_count >= 5 else "warming"
    state["last_updated_at"] = event_time
    updated["stage"] = state["consumer_stage"]
    processed.append(event_id)
    return updated, {
        "event_id": event_id,
        "status": "applied",
        "event_type": event_type,
        "strength": strength,
        "tag_updates": tag_updates,
    }


def apply_publish_event(backpack: dict, post: dict) -> tuple[dict, dict]:
    updated = copy.deepcopy(backpack)
    state = updated["profile_state"]
    event_id = str(post["event_id"])
    processed = state.setdefault("processed_event_ids", [])
    if event_id in processed:
        return updated, {"event_id": event_id, "status": "duplicate_skipped", "tag_updates": []}

    event_time = str(post["event_time"])
    inferred_tags = post.get("tags") or infer_post_tags(post)
    tag_updates = []
    for inferred in inferred_tags:
        name = str(inferred["name"])
        confidence = float(np.clip(inferred.get("confidence", 0.0), 0.0, 1.0))
        tag = _find_tag(updated["creator_tag_bag"], name)
        if tag is None:
            tag = {
                "tag_id": f"creator:{name}",
                "name": name,
                "categories": [name],
                "long_term_weight": 0.0,
                "short_term_weight": 0.0,
                "session_weight": 0.0,
                "negative_weight": 0.0,
                "confidence": confidence,
                "evidence_count": 0,
                "sources": {
                    "registration_selection": 0.0,
                    "behavior": 0.0,
                    "published_post": 0.0,
                },
                "last_event": "publish",
                "updated_at": event_time,
            }
            updated["creator_tag_bag"].append(tag)

        old_values = {
            key: float(tag[key])
            for key in ("long_term_weight", "short_term_weight", "session_weight")
        }
        previous_time = str(tag["updated_at"])
        repeat_decay = 0.7 ** int(tag["evidence_count"])
        delta = PUBLISH_STRENGTH * confidence * repeat_decay
        multipliers = {
            "long_term_weight": 0.60,
            "short_term_weight": 1.00,
            "session_weight": 1.00,
        }
        for key, multiplier in multipliers.items():
            decayed = _decay(old_values[key], previous_time, event_time, CREATOR_DECAY_DAYS[key])
            tag[key] = round(float(np.clip(decayed + delta * multiplier, 0.0, 1.0)), 6)

        count = int(tag["evidence_count"])
        tag["confidence"] = round((float(tag["confidence"]) * count + confidence) / (count + 1), 6)
        tag["evidence_count"] = count + 1
        tag["sources"]["published_post"] = round(
            float(tag["sources"].get("published_post", 0.0)) + delta, 6
        )
        tag["last_event"] = "publish"
        tag["updated_at"] = event_time
        tag_updates.append(
            {
                "tag": name,
                "confidence": confidence,
                "delta": round(delta, 6),
                "before": old_values,
                "after": {
                    key: tag[key]
                    for key in ("long_term_weight", "short_term_weight", "session_weight")
                },
            }
        )

    state["published_post_count"] = int(state.get("published_post_count", 0)) + 1
    state["creator_evidence_count"] = int(state.get("creator_evidence_count", 0)) + len(inferred_tags)
    state["creator_stage"] = "warming"
    state["last_updated_at"] = event_time
    processed.append(event_id)
    updated["creator_tag_bag"].sort(
        key=lambda tag: (tag["long_term_weight"], tag["short_term_weight"]), reverse=True
    )
    return updated, {
        "event_id": event_id,
        "status": "applied",
        "post_id": post["post_id"],
        "tag_updates": tag_updates,
    }
