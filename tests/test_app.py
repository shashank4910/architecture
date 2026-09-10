import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# app imports lazily, so the module itself collects without Flask/Pillow.
import app  # noqa: E402

try:
    import flask  # noqa: F401
    HAS_FLASK = True
except Exception:
    HAS_FLASK = False


def _bank_plan(width, depth, facing, bedrooms, suffix=""):
    """Minimal plan skeleton with the fields the pure helpers read."""
    return {
        "design_id": f"plan_{width}x{depth}_{bedrooms}bhk_{facing}{suffix}",
        "plot": {"width_ft": width, "depth_ft": depth, "facing": facing},
        "bedrooms": bedrooms,
        "rooms": [{"id": "r1", "name": "Living", "kind": "habitable"}],
    }


class PureHelperTests(unittest.TestCase):
    """Bank loading / filtering and path containment run without Flask."""

    def test_iter_bank_plans_reads_json(self):
        with tempfile.TemporaryDirectory() as d:
            bank = Path(d)
            (bank / "a.json").write_text(json.dumps(_bank_plan(20, 50, "north", 2)))
            (bank / "b.json").write_text(json.dumps(_bank_plan(30, 40, "north", 3)))
            plans = app.iter_bank_plans(bank)
        self.assertEqual(len(plans), 2)

    def test_iter_bank_plans_missing_dir_is_empty(self):
        self.assertEqual(app.iter_bank_plans(Path("/no/such/bank/dir")), [])

    def test_filter_bank_exact_match_only(self):
        plans = [
            _bank_plan(20, 50, "north", 2, "a"),
            _bank_plan(20, 50, "north", 3, "b"),
            _bank_plan(20, 50, "east", 2, "c"),
            _bank_plan(30, 40, "north", 2, "d"),
        ]
        out = app.filter_bank(plans, 20, 50, "north", 2)
        self.assertEqual([p["design_id"] for p in out], ["plan_20x50_2bhk_northa"])

    def test_filter_bank_never_relabels_facing(self):
        # An east-facing plan must never satisfy a north request.
        plans = [_bank_plan(20, 50, "east", 2)]
        self.assertEqual(app.filter_bank(plans, 20, 50, "north", 2), [])

    def test_resolve_within_clamps_outside_root(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "out"
            root.mkdir()
            outside = Path(d) / "outside"
            outside.mkdir()
            self.assertEqual(app.resolve_within(str(outside), root), root.resolve())

    def test_resolve_within_allows_descendant(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "out"
            child = root / "batch"
            child.mkdir(parents=True)
            self.assertEqual(app.resolve_within(str(child), root), child.resolve())

    def test_resolve_within_traversal_is_clamped(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "out"
            root.mkdir()
            self.assertEqual(app.resolve_within("../../etc", root), root.resolve())

    def test_no_make_plan_fallback_in_source(self):
        # /generate must never fall back to the legacy make_plan flow.
        source = Path(app.__file__).read_text(encoding="utf-8")
        self.assertNotIn("make_plan", source)

    def test_render_selection_reuses_cache(self):
        calls = []

        def fake_render(plan, path):
            calls.append(Path(path).name)
            Path(path).write_bytes(b"png")

        plan = _bank_plan(20, 50, "north", 2)
        plan["rooms"] = [{
            "id": "r1", "name": "Living", "kind": "habitable",
            "x_ft": 0, "y_ft": 0, "width_ft": 20, "depth_ft": 25,
        }]
        plans = [plan]
        with tempfile.TemporaryDirectory() as d:
            batch = Path(d) / "batch"
            with patch.object(app, "_render_2d", return_value=fake_render):
                first = app.render_selection(plans, batch)
                self.assertEqual(len(first), 1)
                self.assertEqual(len(calls), 1)
                # Second identical run must reuse the cached PNG, not re-render.
                app.render_selection(plans, batch)
                self.assertEqual(len(calls), 1)


@unittest.skipUnless(HAS_FLASK, "Flask not installed in this environment")
class FlaskRouteTests(unittest.TestCase):
    def setUp(self):
        importlib.reload(app)
        self.app = app.create_app()
        self.client = self.app.test_client()

    def test_insufficient_bank_returns_422_with_available_count(self):
        validated = [_bank_plan(20, 50, "north", 2)]  # only 1 available
        with patch.object(app, "iter_bank_plans", return_value=validated), \
             patch.object(app, "select_validated", return_value=validated):
            resp = self.client.post("/generate", data={
                "size": "20x50", "facing": "north", "bedrooms": "2", "quantity": "5",
            })
        self.assertEqual(resp.status_code, 422)
        body = resp.get_data(as_text=True)
        self.assertIn("only 1 validated", body)

    def test_unsupported_facing_rejected(self):
        resp = self.client.post("/generate", data={
            "size": "20x50", "facing": "east", "bedrooms": "2", "quantity": "1",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("north-facing", resp.get_data(as_text=True))

    def test_unsupported_plot_size_rejected(self):
        resp = self.client.post("/generate", data={
            "size": "40x40", "facing": "north", "bedrooms": "2", "quantity": "1",
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Unsupported plot size", resp.get_data(as_text=True))

    def test_valid_request_shows_all_images_not_capped_at_six(self):
        validated = [_bank_plan(20, 50, "north", 2, str(i)) for i in range(8)]
        rendered = [
            {"name": f"img{i}.png", "src": f"/generated_ui/img{i}.png",
             "href": f"/generated_ui/img{i}.png", "design_id": f"d{i}"}
            for i in range(8)
        ]
        with patch.object(app, "iter_bank_plans", return_value=validated), \
             patch.object(app, "select_validated", return_value=validated), \
             patch.object(app, "render_selection", return_value=rendered):
            resp = self.client.post("/generate", data={
                "size": "20x50", "facing": "north", "bedrooms": "2", "quantity": "8",
            })
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        for i in range(8):
            self.assertIn(f"img{i}.png", body)
        self.assertIn(app.CONCEPT_LABEL, body)

    def test_browse_outside_root_is_clamped_and_does_not_raise(self):
        with tempfile.TemporaryDirectory() as d:
            outside = Path(d) / "outside"
            outside.mkdir()
            resp = self.client.get("/browse", query_string={"folder": str(outside)})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("generated/ui", resp.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
