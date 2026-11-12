import unittest

from src.profile_updater import apply_publish_event


class ProfileUpdaterTest(unittest.TestCase):
    def setUp(self):
        self.backpack = {
            "user_id": "u1",
            "consumer_tag_bag": [{"name": "旅行与海滩", "long_term_weight": 1.0}],
            "creator_tag_bag": [],
            "negative_tag_bag": [],
            "profile_state": {
                "published_post_count": 0,
                "last_updated_at": "2026-11-10T10:00:00+08:00",
            },
        }
        self.post = {
            "event_id": "publish:u1:1",
            "post_id": "p1",
            "event_time": "2026-11-11T10:00:00+08:00",
            "text": "我在海滩上冲浪",
            "tags": [{"name": "旅行户外", "confidence": 0.9}],
        }

    def test_publish_updates_creator_bag_only(self):
        updated, result = apply_publish_event(self.backpack, self.post)
        self.assertEqual(result["status"], "applied")
        self.assertEqual(updated["creator_tag_bag"][0]["name"], "旅行户外")
        self.assertGreater(updated["creator_tag_bag"][0]["long_term_weight"], 0)
        self.assertEqual(updated["consumer_tag_bag"], self.backpack["consumer_tag_bag"])
        self.assertEqual(updated["profile_state"]["published_post_count"], 1)

    def test_duplicate_event_is_idempotent(self):
        first, _ = apply_publish_event(self.backpack, self.post)
        second, result = apply_publish_event(first, self.post)
        self.assertEqual(result["status"], "duplicate_skipped")
        self.assertEqual(second["creator_tag_bag"], first["creator_tag_bag"])
        self.assertEqual(second["profile_state"]["published_post_count"], 1)

    def test_repeated_evidence_has_smaller_increment(self):
        first, first_result = apply_publish_event(self.backpack, self.post)
        second_post = dict(self.post)
        second_post["event_id"] = "publish:u1:2"
        second_post["post_id"] = "p2"
        second_post["event_time"] = "2026-11-11T11:00:00+08:00"
        _, second_result = apply_publish_event(first, second_post)
        first_delta = first_result["tag_updates"][0]["delta"]
        second_delta = second_result["tag_updates"][0]["delta"]
        self.assertLess(second_delta, first_delta)


if __name__ == "__main__":
    unittest.main()
