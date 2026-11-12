import unittest

from src.cold_start import (
    deterministic_exploration,
    interest_affinity,
    parse_interests,
    region_affinity,
    score_components,
)


class ColdStartTest(unittest.TestCase):
    def test_parse_and_normalize_interests(self):
        names, weights = parse_interests(
            {"selected_interests": [{"name": "旅行", "weight": 2}, "摄影"]}
        )
        self.assertEqual(names, ["旅行", "摄影"])
        self.assertAlmostEqual(float(weights.sum()), 1.0)
        self.assertGreater(weights[0], weights[1])

    def test_region_is_neutral_without_content_region(self):
        self.assertEqual(region_affinity({"region": "上海"}, {}), 0.5)
        self.assertEqual(region_affinity({"region": "上海"}, {"regions": ["上海"]}), 1.0)

    def test_score_is_deterministic(self):
        profile = {"user_id": "u1", "region": "北京"}
        item = {"id": "p1", "popularity": 0.8, "quality": 0.9}
        first = score_components(0.5, profile, item)
        second = score_components(0.5, profile, item)
        self.assertEqual(first, second)
        self.assertEqual(
            deterministic_exploration("u1", "p1"), deterministic_exploration("u1", "p1")
        )

    def test_explicit_interest_category_increases_score(self):
        profile = {
            "user_id": "u1",
            "selected_interests": [{"name": "网球和体育运动", "weight": 1.0}],
        }
        affinity, categories = interest_affinity(profile, {"text": "运动员在球场挥拍打网球"})
        self.assertEqual(affinity, 1.0)
        self.assertIn("体育运动", categories)
        matched = score_components(0.3, profile, {"id": "a"}, interest_match=affinity)
        unmatched = score_components(0.3, profile, {"id": "a"}, interest_match=0.0)
        self.assertGreater(matched["total"], unmatched["total"])

    def test_toilet_does_not_match_horse_interest(self):
        profile = {"selected_interests": ["动物和骑马"]}
        affinity, categories = interest_affinity(profile, {"text": "卫生间里有一个马桶"})
        self.assertEqual(affinity, 0.0)
        self.assertEqual(categories, [])


if __name__ == "__main__":
    unittest.main()
