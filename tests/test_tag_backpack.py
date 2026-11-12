import tempfile
import unittest
from pathlib import Path

from src.tag_backpack import build_initial_tag_backpack, create_initial_tag_backpacks


class TagBackpackTest(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "user_id": "u1",
            "age": 22,
            "gender": "女",
            "region": "上海",
            "selected_interests": [
                {"name": "旅行与海滩", "weight": 1.0},
                {"name": "摄影", "weight": 0.7},
            ],
        }

    def test_initial_bag_keeps_demographics_out_of_interest_tags(self):
        bag = build_initial_tag_backpack(self.profile, "2026-11-10T10:00:00+08:00")
        names = [tag["name"] for tag in bag["consumer_tag_bag"]]
        self.assertEqual(names, ["旅行与海滩", "摄影"])
        self.assertNotIn("女", names)
        self.assertNotIn("上海", names)
        self.assertFalse(bag["demographic_context"]["ranking_policy"]["gender_direct_ranking"])

    def test_initial_bag_is_ready_for_behavior_updates(self):
        bag = build_initial_tag_backpack(self.profile, "2026-11-10T10:00:00+08:00")
        first = bag["consumer_tag_bag"][0]
        self.assertEqual(first["long_term_weight"], 1.0)
        self.assertEqual(first["short_term_weight"], 0.0)
        self.assertEqual(first["session_weight"], 0.0)
        self.assertEqual(first["sources"]["behavior"], 0.0)
        self.assertEqual(bag["creator_tag_bag"], [])

    def test_write_jsonl(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            users = root / "users.jsonl"
            output = root / "bags.jsonl"
            users.write_text(
                '{"user_id":"u1","selected_interests":["科技"]}\n', encoding="utf-8"
            )
            bags = create_initial_tag_backpacks(
                users, output, generated_at="2026-11-10T10:00:00+08:00"
            )
            self.assertEqual(len(bags), 1)
            self.assertEqual(len(output.read_text(encoding="utf-8").splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
