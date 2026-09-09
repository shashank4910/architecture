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

    def test_08_bedroom_accessed_through_bedroom_fails(self):
        plan = deepcopy(self.valid)
        plan["doors"].append({
            "id": "bed2_master_private",
            "room_id": "bed2",
            "side": "east",
            "offset_ft": 2,
            "connects_to": "master",
        })
        result = validate_plan(plan)
        self.assertEqual(result["overall"], "FAIL")
        self.assertTrue(any("private-private" in error for error in result["errors"]))

    def test_09_master_bedroom_access_from_circulation_passes(self):
        self.assertEqual(validate_plan(self.valid)["overall"], "PASS")

    def test_10_common_bathroom_access_from_circulation_passes(self):
        result = validate_plan(self.valid)
        self.assertEqual(result["overall"], "PASS")
        self.assertTrue(any(room["id"] == "bath1" for room in self.valid["rooms"]))

    def test_11_bathroom_accessible_only_through_bedroom_fails(self):
        plan = deepcopy(self.valid)
        room = next(item for item in plan["rooms"] if item["id"] == "bath2")
        room.pop("ensuite_of", None)
        plan["doors"].append({
            "id": "bed2_bath2_private",
            "room_id": "bed2",
            "side": "south",
            "offset_ft": 1,
            "connects_to": "bath2",
        })
        result = validate_plan(plan)
        self.assertEqual(result["overall"], "FAIL")
        self.assertTrue(any("bathroom" in error for error in result["errors"]))

    def test_12_staircase_accessed_through_bedroom_fails(self):
        plan = deepcopy(self.valid)
        plan["doors"].append({
            "id": "bed2_stair_private",
            "room_id": "bed2",
            "side": "north",
            "offset_ft": 1,
            "connects_to": "staircase",
        })
        result = validate_plan(plan)
        self.assertEqual(result["overall"], "FAIL")
        self.assertTrue(any("staircase" in error for error in result["errors"]))

    def test_13_kitchen_accessed_through_bedroom_fails(self):
        plan = {
            "design_id": "mini_private_kitchen",
            "plot": {"width_ft": 20, "depth_ft": 20, "facing": "north"},
            "rooms": [
                {"id": "living", "name": "Living", "x_ft": 0, "y_ft": 0, "width_ft": 20, "depth_ft": 8, "kind": "habitable"},
                {"id": "corridor", "name": "Corridor", "x_ft": 0, "y_ft": 8, "width_ft": 20, "depth_ft": 2, "kind": "circulation"},
                {"id": "bed1", "name": "Bedroom 1", "x_ft": 0, "y_ft": 10, "width_ft": 8, "depth_ft": 10, "kind": "habitable"},
                {"id": "kitchen", "name": "Kitchen", "x_ft": 8, "y_ft": 10, "width_ft": 12, "depth_ft": 5, "kind": "kitchen"},
                {"id": "bath", "name": "Bathroom", "x_ft": 8, "y_ft": 15, "width_ft": 6, "depth_ft": 5, "kind": "bathroom"},
            ],
            "doors": [
                {"id": "entrance", "room_id": "living", "side": "north", "offset_ft": 5, "connects_to": "exterior"},
                {"id": "living_corridor", "room_id": "living", "side": "south", "offset_ft": 6, "connects_to": "corridor"},
                {"id": "corridor_bed1", "room_id": "corridor", "side": "south", "offset_ft": 5, "connects_to": "bed1"},
                {"id": "bed1_kitchen", "room_id": "bed1", "side": "east", "offset_ft": 2, "connects_to": "kitchen"},
                {"id": "kitchen_bath", "room_id": "kitchen", "side": "south", "offset_ft": 1, "connects_to": "bath"},
            ],
            "windows": [],
            "stairs": [],
            "parking": [],
        }
        result = validate_plan(plan)
        self.assertEqual(result["overall"], "FAIL")
        self.assertTrue(any("room kitchen" in error or "kitchen" in error for error in result["errors"]))

    def test_14_living_to_circulation_to_bedroom_passes(self):
        result = validate_plan(self.valid)
        self.assertEqual(result["overall"], "PASS")


if __name__ == "__main__":
    unittest.main()
