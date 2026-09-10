"""Focused tests for genuine ensuite (attached bathroom) support.

Confirms an ensuite bath is accepted end-to-end and that the privacy gate still
rejects a common bathroom reached only through a bedroom.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from house_plan_generator.bulk_assembly import assemble_layout
from house_plan_generator.catalog_validation import validate_catalog_plan
from house_plan_generator.validator import validate_plan


def _seed(seed_id):
    for seed in json.loads((ROOT / "data" / "structural_seeds.json").read_text()):
        if seed.get("seed_id") == seed_id:
            return seed
    raise KeyError(seed_id)


class EnsuiteSupportTests(unittest.TestCase):
    def test_ensuite_seed_assembles_and_passes_all_gates(self):
        seed = _seed("E04")
        plan, err = assemble_layout(
            seed["raw"], seed["width"], seed["depth"],
            seed["bedrooms"], seed["store"], seed["assembly_seed"],
        )
        self.assertIsNone(err)
        plan["design_id"] = "test_e04"
        bath2 = next(r for r in plan["rooms"] if r["id"] == "bath2")
        self.assertEqual(bath2.get("ensuite_of"), "master")
        # The ensuite bath's only door is to its owning bedroom.
        neighbours = set()
        for door in plan["doors"]:
            if door["room_id"] == "bath2":
                neighbours.add(door["connects_to"])
            if door["connects_to"] == "bath2":
                neighbours.add(door["room_id"])
        self.assertEqual(neighbours, {"master"})
        self.assertEqual(validate_catalog_plan(plan)["overall"], "PASS")

    def test_genuine_ensuite_is_allowed_by_privacy_gate(self):
        plan = {
            "plot": {"width_ft": 20, "depth_ft": 20, "facing": "north"},
            "rooms": [
                {"id": "living", "kind": "circulation", "name": "Living", "x_ft": 0, "y_ft": 0, "width_ft": 20, "depth_ft": 8},
                {"id": "master", "kind": "habitable", "name": "Master bedroom", "x_ft": 0, "y_ft": 8, "width_ft": 12, "depth_ft": 12},
                {"id": "bath2", "kind": "bathroom", "name": "Attached Bath", "x_ft": 12, "y_ft": 8, "width_ft": 8, "depth_ft": 12, "ensuite_of": "master"},
            ],
            "doors": [
                {"id": "entrance", "room_id": "living", "connects_to": "exterior", "side": "north", "offset_ft": 1, "width_ft": 3},
                {"id": "d1", "room_id": "living", "connects_to": "master", "side": "south", "offset_ft": 1, "width_ft": 3},
                {"id": "d2", "room_id": "master", "connects_to": "bath2", "side": "east", "offset_ft": 1, "width_ft": 3},
            ],
        }
        res = validate_plan(plan)
        self.assertTrue(res["privacy_valid"])
        self.assertTrue(res["access_valid"])

    def test_common_bath_through_bedroom_still_rejected(self):
        plan = {
            "plot": {"width_ft": 20, "depth_ft": 20, "facing": "north"},
            "rooms": [
                {"id": "living", "kind": "circulation", "name": "Living", "x_ft": 0, "y_ft": 0, "width_ft": 20, "depth_ft": 8},
                {"id": "master", "kind": "habitable", "name": "Master bedroom", "x_ft": 0, "y_ft": 8, "width_ft": 12, "depth_ft": 12},
                {"id": "bath1", "kind": "bathroom", "name": "Common Bath", "x_ft": 12, "y_ft": 8, "width_ft": 8, "depth_ft": 12},
            ],
            "doors": [
                {"id": "entrance", "room_id": "living", "connects_to": "exterior", "side": "north", "offset_ft": 1, "width_ft": 3},
                {"id": "d1", "room_id": "living", "connects_to": "master", "side": "south", "offset_ft": 1, "width_ft": 3},
                {"id": "d2", "room_id": "master", "connects_to": "bath1", "side": "east", "offset_ft": 1, "width_ft": 3},
            ],
        }
        res = validate_plan(plan)
        self.assertEqual(res["overall"], "FAIL")
        self.assertTrue(any("ensuite" in e or "bathroom" in e for e in res["errors"]))


if __name__ == "__main__":
    unittest.main()
