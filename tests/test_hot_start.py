import unittest

from src.hot_start import _ranking_metrics, category_profile, recommend_hot_start
from src.profile_updater import apply_consumer_event


class HotStartTest(unittest.TestCase):
    def setUp(self):
        self.backpack = {
            "user_id": "u1",
            "stage": "cold_start",
            "consumer_tag_bag": [],
            "creator_tag_bag": [],
            "negative_tag_bag": [],
            "profile_state": {
                "effective_behavior_count": 0,
                "last_updated_at": "2026-11-11T09:00:00+08:00",
            },
        }
        self.event = {
            "event_id": "e1",
            "event_type": "save",
            "event_time": "2026-11-12T09:00:00+08:00",
            "text": "球场上的网球比赛",
            "tags": [{"name": "体育运动", "confidence": 0.9}],
        }

    def test_positive_behavior_updates_consumer_only(self):
        updated, result = apply_consumer_event(self.backpack, self.event)
        self.assertEqual(result["status"], "applied")
        self.assertEqual(updated["consumer_tag_bag"][0]["name"], "体育运动")
        self.assertGreater(updated["consumer_tag_bag"][0]["session_weight"], 0)
        self.assertEqual(updated["creator_tag_bag"], [])

    def test_negative_behavior_is_separate(self):
        event = dict(self.event, event_id="e2", event_type="not_interested")
        updated, _ = apply_consumer_event(self.backpack, event)
        self.assertEqual(updated["consumer_tag_bag"], [])
        self.assertGreater(updated["negative_tag_bag"][0]["negative_weight"], 0)

    def test_duplicate_event_is_idempotent(self):
        first, _ = apply_consumer_event(self.backpack, self.event)
        second, result = apply_consumer_event(first, self.event)
        self.assertEqual(result["status"], "duplicate_skipped")
        self.assertEqual(first, second)

    def test_updated_profile_changes_ranking(self):
        updated, _ = apply_consumer_event(self.backpack, self.event)
        candidates = [
            {"id": "sport", "text": "运动员在球场打网球"},
            {"id": "food", "text": "厨房里放着蛋糕和披萨"},
        ]
        result = recommend_hot_start(updated, candidates, top_k=2)
        self.assertEqual(result[0]["ugc_id"], "sport")
        self.assertGreater(category_profile(updated)["体育运动"], 0)

    def test_ndcg_stays_in_unit_interval(self):
        recommendations = [
            {"categories": ["体育运动"]},
            {"categories": ["美食烹饪"]},
            {"categories": ["体育运动"]},
        ]
        metrics = _ranking_metrics(recommendations, {"体育运动": 1.0})
        self.assertGreaterEqual(metrics["ndcg_at_5"], 0.0)
        self.assertLessEqual(metrics["ndcg_at_5"], 1.0)


if __name__ == "__main__":
    unittest.main()
