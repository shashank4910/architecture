from pathlib import Path
import tempfile
import unittest

from PIL import Image

from house_plan_generator.plan_data import get_plans
from house_plan_generator.renderer_2d import render_2d


class RendererTests(unittest.TestCase):
    def test_all_ten_plans_render_and_preserve_manifest_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            for plan in get_plans():
                output = Path(directory) / f"{plan['design_id']}.png"
                manifest = render_2d(plan, output)
                self.assertTrue(output.exists())
                with Image.open(output) as image:
                    self.assertGreater(image.width, 900)
                    self.assertGreater(image.height, 900)
                    self.assertIsNotNone(image.getbbox())
                self.assertEqual([room["id"] for room in manifest["rooms"]], [room["id"] for room in plan["rooms"]])
                for rendered, canonical in zip(manifest["rooms"], plan["rooms"]):
                    for key in ("x_ft", "y_ft", "width_ft", "depth_ft"):
                        self.assertEqual(rendered[key], canonical[key])

    def test_rendered_plan_contains_required_annotation_inputs(self):
        plan = get_plans()[0]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "plan.png"
            render_2d(plan, output)
            with Image.open(output) as image:
                colors = image.convert("RGB").getcolors(maxcolors=10_000_000)
            self.assertGreater(len(colors), 20)
            self.assertTrue(plan["doors"])
            self.assertTrue(plan["windows"])
            self.assertTrue(any(room["id"] == "staircase" for room in plan["rooms"]))
            self.assertTrue(any(room["id"] == "parking" for room in plan["rooms"]))


if __name__ == "__main__":
    unittest.main()
