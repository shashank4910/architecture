from copy import deepcopy
import unittest

from house_plan_generator.match_validator import compare_geometry
from house_plan_generator.plan_data import get_plans
from house_plan_generator.renderer_2d import render_2d
from house_plan_generator.renderer_3d import render_3d


class MatchValidatorTests(unittest.TestCase):
    def test_2d_and_3d_match_canonical_geometry(self):
        plan = get_plans()[0]
        geometry_2d = {"plot": plan["plot"], "rooms": [{key: room[key] for key in ("id", "x_ft", "y_ft", "width_ft", "depth_ft")} for room in plan["rooms"]]}
        geometry_3d = deepcopy(geometry_2d)
        self.assertTrue(compare_geometry(plan, geometry_2d, geometry_3d)["matched"])

    def test_moved_room_fails_match(self):
        plan = get_plans()[0]
        geometry = {"plot": plan["plot"], "rooms": [{key: room[key] for key in ("id", "x_ft", "y_ft", "width_ft", "depth_ft")} for room in plan["rooms"]]}
        moved = deepcopy(geometry)
        moved["rooms"][0]["x_ft"] += 1
        result = compare_geometry(plan, geometry, moved)
        self.assertFalse(result["matched"])
        self.assertTrue(any("3D" in issue or "room position" in issue for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
