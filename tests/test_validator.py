from copy import deepcopy
import unittest

from house_plan_generator.plan_data import get_plans
from house_plan_generator.validator import validate_plan


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.valid = get_plans()[0]

    def assert_fails(self, mutate, text):
        plan = deepcopy(self.valid)
        mutate(plan)
        result = validate_plan(plan)
        self.assertEqual(result["overall"], "FAIL", text)

    def test_01_room_outside_plot(self):
        self.assert_fails(lambda p: p["rooms"][0].update({"x_ft": 19, "width_ft": 5}), "outside room")

    def test_02_overlapping_rooms(self):
        self.assert_fails(lambda p: p["rooms"].append({"id": "bad", "name": "Bad", "x_ft": 10, "y_ft": 0, "width_ft": 10, "depth_ft": 12}), "overlap")

    def test_03_zero_bathroom_dimensions(self):
        self.assert_fails(lambda p: p["rooms"][-1].update({"width_ft": 0}), "zero dimension")

    def test_04_isolated_room(self):
        self.assert_fails(lambda p: p["doors"].clear(), "isolated room")

    def test_05_staircase_overlap(self):
        self.assert_fails(lambda p: p["rooms"].append({"id": "bad_stair", "name": "Bad Stair", "x_ft": 0, "y_ft": 24, "width_ft": 6, "depth_ft": 9, "kind": "staircase"}), "stair overlap")

    def test_06_valid_20x50_layout(self):
        self.assertEqual(validate_plan(get_plans()[0])["overall"], "PASS")

    def test_07_valid_30x40_layout(self):
        self.assertEqual(validate_plan(get_plans()[3])["overall"], "PASS")


if __name__ == "__main__":
    unittest.main()
