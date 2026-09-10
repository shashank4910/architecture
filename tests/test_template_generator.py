"""Tests for the strategy-driven template generator.

These lock the generator's contract: exact tiling is enforced, every approved
parameter combination tiles the plot, the existing gates are actually run, and
duplicates/near-duplicates of the accepted bank are rejected (never faked).
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from house_plan_generator import template_library
from house_plan_generator.catalog_diversity import DiversityIndex
from house_plan_generator.template_generator import (
    MasterTemplate, generate_from_template, tiling_error,
)


class TilingTests(unittest.TestCase):
    def test_every_template_combination_tiles_exactly(self):
        for template in template_library.TEMPLATES:
            for values in template.combinations():
                rooms = template.layout(values)
                err = tiling_error(rooms, template.width, template.depth)
                self.assertIsNone(
                    err, f"{template.template_id} {values}: {err}")

    def test_tiling_error_detects_gap(self):
        rooms = {"a": [0, 0, 10, 10]}  # only covers part of a 20x20 plot
        self.assertIsNotNone(tiling_error(rooms, 20, 20))

    def test_tiling_error_detects_overlap(self):
        rooms = {"a": [0, 0, 20, 20], "b": [0, 0, 5, 5]}
        self.assertIsNotNone(tiling_error(rooms, 20, 20))


class GeneratorContractTests(unittest.TestCase):
    def test_generator_never_exceeds_cap(self):
        template = template_library.TEMPLATES[0]
        index = DiversityIndex()
        _, report = generate_from_template(template, index, max_candidates=3)
        self.assertLessEqual(report["candidates_attempted"], 3)

    def test_duplicate_is_rejected_not_faked(self):
        # A template whose only candidate reproduces an already-indexed plan must
        # be rejected by the diversity gate, never accepted as a "new" plan.
        template = template_library.TEMPLATES[0]
        first_values = next(template.combinations())
        index = DiversityIndex()
        accepted, _ = generate_from_template(template, index, max_candidates=10)
        # Re-running against an index already containing the accepted output yields
        # zero new accepted plans (they are duplicates/near-duplicates now).
        accepted2, report2 = generate_from_template(template, index, max_candidates=10)
        self.assertEqual(len(accepted2), 0)
        self.assertTrue(any("diversity" in k for k in report2["rejections"]))

    def test_accepted_plans_are_valid_and_diverse(self):
        # Whatever the generator accepts must pass validation and be added to the
        # index without raising (i.e. it is genuinely distinct at accept time).
        from house_plan_generator.catalog_validation import validate_catalog_plan
        for template in template_library.TEMPLATES:
            index = DiversityIndex()
            accepted, _ = generate_from_template(template, index, max_candidates=10)
            for plan in accepted:
                self.assertEqual(validate_catalog_plan(plan)["overall"], "PASS")


if __name__ == "__main__":
    unittest.main()
