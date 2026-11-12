from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

from .encoder import MultimodalEncoder, normalize


DEFAULT_WEIGHTS = {
    "semantic": 0.68,
    "interest_match": 0.18,
    "popularity": 0.05,
    "quality": 0.05,
    "region": 0.02,
    "exploration": 0.02,
}


CATEGORY_KEYWORDS = {
    "旅行户外": ("旅行", "海滩", "海边", "冲浪", "户外", "湖", "帐篷", "风景"),
    "体育运动": ("体育", "运动", "网球", "球拍", "球场", "滑雪", "冲浪", "棒球", "足球"),
    "美食烹饪": ("美食", "烹饪", "餐厅", "食物", "吃", "厨房", "披萨", "蛋糕", "三明治", "热狗", "奶酪"),
    "交通工具": ("汽车", "火车", "交通", "道路", "摩托", "飞机", "公交", "卡车", "自行车"),
    "动物自然": (
        "动物", "自然", "狗", "猫", "鸟", "骑马", "马匹", "一匹马", "奶牛", "牛群", "绵羊",
        "大象", "熊", "长颈鹿", "斑马", "树", "花", "草", "山",
    ),
    "科技数码": ("科技", "电子", "电脑", "办公", "笔记本", "手机", "电视", "键盘", "显示器"),
}


def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def parse_interests(profile: dict) -> tuple[list[str], np.ndarray]:
    names: list[str] = []
    weights: list[float] = []
    for value in profile.get("selected_interests", []):
        if isinstance(value, str):
            name, weight = value, 1.0
        else:
            name = str(value.get("name", ""))
            weight = float(value.get("weight", 1.0))
        if name.strip() and weight > 0:
            names.append(name.strip())
            weights.append(weight)
    if not names:
        return [], np.empty(0, dtype=np.float32)
    array = np.asarray(weights, dtype=np.float32)
    return names, array / array.sum()


def build_interest_prompts(names: Iterable[str]) -> list[str]:
    return [f"用户感兴趣的社交内容：{name}" for name in names]


def deterministic_exploration(user_id: str, item_id: str) -> float:
    digest = hashlib.sha256(f"{user_id}:{item_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") / (2**32 - 1)


def infer_categories(text: str) -> set[str]:
    value = str(text)
    return {
        category
        for category, keywords in CATEGORY_KEYWORDS.items()
        if any(keyword in value for keyword in keywords)
    }


def interest_affinity(profile: dict, item: dict) -> tuple[float, list[str]]:
    names, weights = parse_interests(profile)
    item_categories = infer_categories(str(item.get("text", "")))
    if not names or not item_categories:
        return 0.0, []
    matched: set[str] = set()
    score = 0.0
    for name, weight in zip(names, weights):
        overlap = infer_categories(name) & item_categories
        if overlap:
            matched.update(overlap)
            score += float(weight)
    return min(score, 1.0), sorted(matched)


def region_affinity(profile: dict, item: dict) -> float:
    user_region = str(profile.get("region", "")).strip()
    item_regions = item.get("regions", [])
    if isinstance(item_regions, str):
        item_regions = [item_regions]
    values = {str(value).strip() for value in item_regions if str(value).strip()}
    if not user_region or not values:
        return 0.5
    return 1.0 if user_region in values else 0.0


def score_components(
    semantic_similarity: float,
    profile: dict,
    item: dict,
    interest_match: float = 0.0,
    weights: Optional[dict[str, float]] = None,
) -> dict[str, float]:
    active = weights or DEFAULT_WEIGHTS
    semantic = float(np.clip((semantic_similarity + 1.0) / 2.0, 0.0, 1.0))
    popularity = float(np.clip(item.get("popularity", 0.5), 0.0, 1.0))
    quality = float(np.clip(item.get("quality", 0.7), 0.0, 1.0))
    region = region_affinity(profile, item)
    exploration = deterministic_exploration(str(profile["user_id"]), str(item["id"]))
    total = (
        active["semantic"] * semantic
        + active["interest_match"] * interest_match
        + active["popularity"] * popularity
        + active["quality"] * quality
        + active["region"] * region
        + active["exploration"] * exploration
    )
    return {
        "semantic": round(semantic, 6),
        "interest_match": round(float(interest_match), 6),
        "popularity": round(popularity, 6),
        "quality": round(quality, 6),
        "region": round(region, 6),
        "exploration": round(exploration, 6),
        "total": round(float(total), 6),
    }


def _batched(values: list, batch_size: int) -> Iterable[list]:
    for start in range(0, len(values), batch_size):
        yield values[start : start + batch_size]


def _encode_candidates(
    encoder: MultimodalEncoder,
    records: list[dict],
    root: Path,
    batch_size: int,
) -> np.ndarray:
    text_vectors = np.concatenate(
        [encoder.encode_texts([str(item.get("text", "")) for item in batch]) for batch in _batched(records, batch_size)]
    )
    image_paths = [(root / item["image"]).resolve() for item in records]
    image_vectors = np.concatenate(
        [encoder.encode_images(batch) for batch in _batched(image_paths, batch_size)]
    )
    return normalize(text_vectors + image_vectors)


def _encode_profiles(encoder: MultimodalEncoder, profiles: list[dict]) -> np.ndarray:
    vectors = []
    for profile in profiles:
        names, interest_weights = parse_interests(profile)
        if names:
            interest_vectors = encoder.encode_texts(build_interest_prompts(names))
            vector = np.sum(interest_vectors * interest_weights[:, None], axis=0)
        else:
            vector = encoder.encode_texts(["优质、热门、多样的社交内容"])[0]
        vectors.append(vector)
    return normalize(np.stack(vectors))


def recommend_cold_start(
    users_path: Path,
    candidates_path: Path,
    top_k: int = 5,
    batch_size: int = 16,
    device: Optional[str] = None,
) -> dict:
    profiles = load_jsonl(users_path)
    candidates = load_jsonl(candidates_path)
    if not profiles:
        raise ValueError("用户画像文件为空")
    if not candidates:
        raise ValueError("候选 UGC 文件为空")
    if any("image" not in item for item in candidates):
        raise ValueError("最小冷启动实验要求每条候选 UGC 都包含 image 字段")

    encoder = MultimodalEncoder(device=device)
    profile_vectors = _encode_profiles(encoder, profiles)
    candidate_vectors = _encode_candidates(encoder, candidates, candidates_path.parent, batch_size)
    similarities = np.sum(profile_vectors[:, None, :] * candidate_vectors[None, :, :], axis=-1)

    users = []
    for user_index, profile in enumerate(profiles):
        names, _ = parse_interests(profile)
        ranked = []
        for item_index, item in enumerate(candidates):
            affinity, matched_categories = interest_affinity(profile, item)
            components = score_components(
                similarities[user_index, item_index], profile, item, interest_match=affinity
            )
            ranked.append((components["total"], item, components, matched_categories))
        ranked.sort(key=lambda value: value[0], reverse=True)
        recommendations = []
        for rank, (_, item, components, matched_categories) in enumerate(
            ranked[: min(top_k, len(ranked))], start=1
        ):
            recommendations.append(
                {
                    "rank": rank,
                    "ugc_id": item["id"],
                    "text": item.get("text", ""),
                    "image": item.get("image", ""),
                    "score": components["total"],
                    "score_detail": components,
                    "matched_categories": matched_categories,
                    "reason": (
                        f"匹配兴趣类别（{'、'.join(matched_categories)}），并与初选兴趣的图文语义接近"
                        if matched_categories
                        else f"与初选兴趣（{'、'.join(names) or '暂无'}）的图文语义接近"
                    ),
                }
            )
        users.append(
            {
                "user_id": profile["user_id"],
                "initial_profile": profile,
                "recommendations": recommendations,
            }
        )
    return {
        "task": "cold_start_recommendation",
        "users": len(profiles),
        "candidates": len(candidates),
        "top_k": top_k,
        "model": "Chinese-CLIP ViT-B/16",
        "score_weights": DEFAULT_WEIGHTS,
        "demographic_policy": (
            "性别和年龄仅作为画像字段保存，当前不直接参与排序；地区仅在内容存在地域字段时弱加权。"
        ),
        "results": users,
    }


def save_recommendations(result: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
