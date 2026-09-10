"""Diversity filter checks on small dict fixtures.

geometry_key / family_key are pure-Python, but the near-duplicate raster
comparison in DiversityIndex requires numpy. When numpy is unavailable (this
sandbox), the raster-dependent tests skip so the module still collects; run
them locally with the .venv.
"""
from copy import deepcopy
import unittest

from house_plan_generator.catalog_diversity import geometry_key, family_key, DiversityIndex

try:
    import numpy  # noqa: F401
    HAVE_NUMPY = True
except Exception:
    HAVE_NUMPY = False


def base_plan():
    """A small 20x50 two-room-ish plan sufficient for geometry/family keys."""
    return {
        'plot': {'width_ft': 20, 'depth_ft': 50, 'facing': 'north'},
        'bedrooms': 2,
        'rooms': [
            {'id': 'living', 'kind': 'habitable', 'role': 'living', 'name': 'Living', 'x_ft': 0, 'y_ft': 0, 'width_ft': 20, 'depth_ft': 20},
            {'id': 'kitchen', 'kind': 'kitchen', 'role': 'kitchen', 'name': 'Kitchen', 'x_ft': 0, 'y_ft': 20, 'width_ft': 10, 'depth_ft': 10},
            {'id': 'master', 'kind': 'habitable', 'role': 'bedroom', 'name': 'Master bedroom', 'x_ft': 10, 'y_ft': 20, 'width_ft': 10, 'depth_ft': 10},
            {'id': 'bed2', 'kind': 'habitable', 'role': 'bedroom', 'name': 'Bedroom 2', 'x_ft': 0, 'y_ft': 30, 'width_ft': 20, 'depth_ft': 20},
        ],
        'doors': [
            {'id': 'd1', 'room_id': 'living', 'connects_to': 'kitchen', 'side': 'south', 'offset_ft': 1, 'width_ft': 3},
            {'id': 'd2', 'room_id': 'living', 'connects_to': 'master', 'side': 'south', 'offset_ft': 12, 'width_ft': 3},
            {'id': 'd3', 'room_id': 'kitchen', 'connects_to': 'bed2', 'side': 'south', 'offset_ft': 1, 'width_ft': 3},
        ],
    }


def mirror_x(plan):
    p = deepcopy(plan)
    w = p['plot']['width_ft']
    for r in p['rooms']:
        r['x_ft'] = w - r['x_ft'] - r['width_ft']
    return p


def mirror_y(plan):
    p = deepcopy(plan)
    d = p['plot']['depth_ft']
    for r in p['rooms']:
        r['y_ft'] = d - r['y_ft'] - r['depth_ft']
    return p


class GeometryKeyTests(unittest.TestCase):
    def test_x_mirror_collapses_to_same_key(self):
        self.assertEqual(geometry_key(base_plan()), geometry_key(mirror_x(base_plan())))

    def test_y_mirror_collapses_to_same_key(self):
        self.assertEqual(geometry_key(base_plan()), geometry_key(mirror_y(base_plan())))

    def test_rename_and_style_only_change_collapses(self):
        p = base_plan()
        for r in p['rooms']:
            r['name'] = r['name'].upper() + ' (renovated)'
            r['label_font_size'] = 22
        p['design_id'] = 'totally-different-id'
        self.assertEqual(geometry_key(base_plan()), geometry_key(p))

    def test_distinct_layout_differs(self):
        p = base_plan()
        # Genuinely move a room to a different zone and resize it.
        p['rooms'][1].update(x_ft=10, y_ft=20, width_ft=10, depth_ft=15)
        p['rooms'][2].update(x_ft=0, y_ft=20, width_ft=10, depth_ft=15)
        self.assertNotEqual(geometry_key(base_plan()), geometry_key(p))

    def test_family_key_mirror_invariant(self):
        self.assertEqual(family_key(base_plan()), family_key(mirror_x(base_plan())))

    def test_family_cap_enforced(self):
        # The family-limit branch of check() runs before any raster comparison,
        # so it needs no numpy.
        idx = DiversityIndex(family_limit=8)
        size = (20, 50)
        idx.families[(size, family_key(base_plan()))] = 8
        reason, _ = idx.check(base_plan())
        self.assertEqual(reason, 'family_limit')


@unittest.skipUnless(HAVE_NUMPY, 'numpy required for raster near-duplicate comparison; run locally with .venv')
class DiversityIndexTests(unittest.TestCase):
    def test_exact_mirror_rejected_as_duplicate(self):
        idx = DiversityIndex()
        idx.add(base_plan())
        reason, _ = idx.check(mirror_x(base_plan()))
        self.assertEqual(reason, 'duplicate_or_mirror')

    def test_rename_style_only_rejected_as_duplicate(self):
        idx = DiversityIndex()
        idx.add(base_plan())
        p = base_plan()
        for r in p['rooms']:
            r['name'] = 'X'
        p['design_id'] = 'other'
        reason, _ = idx.check(p)
        self.assertEqual(reason, 'duplicate_or_mirror')

    def test_tiny_shift_rejected_as_near_duplicate(self):
        idx = DiversityIndex()
        idx.add(base_plan())
        p = base_plan()
        # A half-foot shift: not an exact geometry key, but well above threshold.
        p['rooms'][2]['x_ft'] = 10.5
        p['rooms'][2]['width_ft'] = 9.5
        reason, score = idx.check(p)
        self.assertEqual(reason, 'near_duplicate')
        self.assertGreaterEqual(score, idx.threshold)

    def test_distinct_layout_accepted(self):
        idx = DiversityIndex()
        idx.add(base_plan())
        p = base_plan()
        p['rooms'] = [
            {'id': 'living', 'kind': 'habitable', 'role': 'living', 'name': 'Living', 'x_ft': 0, 'y_ft': 0, 'width_ft': 20, 'depth_ft': 10},
            {'id': 'kitchen', 'kind': 'kitchen', 'role': 'kitchen', 'name': 'Kitchen', 'x_ft': 0, 'y_ft': 10, 'width_ft': 10, 'depth_ft': 15},
            {'id': 'master', 'kind': 'habitable', 'role': 'bedroom', 'name': 'Master bedroom', 'x_ft': 10, 'y_ft': 10, 'width_ft': 10, 'depth_ft': 15},
            {'id': 'bed2', 'kind': 'habitable', 'role': 'bedroom', 'name': 'Bedroom 2', 'x_ft': 0, 'y_ft': 25, 'width_ft': 20, 'depth_ft': 25},
        ]
        reason, score = idx.check(p)
        self.assertIsNone(reason)


if __name__ == '__main__':
    unittest.main()
