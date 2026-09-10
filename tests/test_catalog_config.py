"""Pure-Python checks on the catalogue quota config; no numpy/PIL/ortools needed."""
import json
from pathlib import Path
import tempfile
import unittest

from house_plan_generator.catalog import read_config

TARGETS = Path(__file__).resolve().parents[1] / 'data/catalog_targets.json'

# Exact BHK mix from AI_HANDOFF section 4 (plot, bedrooms, store) -> count.
EXPECTED_MIX = {
    (20, 50, 2, False): 51,
    (20, 50, 2, True): 9,
    (20, 50, 3, False): 40,
    (30, 40, 2, False): 35,
    (30, 40, 2, True): 5,
    (30, 40, 3, False): 50,
    (30, 40, 3, True): 10,
    (30, 50, 3, False): 55,
    (30, 50, 3, True): 10,
    (30, 50, 4, False): 30,
    (30, 50, 4, True): 5,
}


class CatalogConfigTests(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads(TARGETS.read_text())

    def _write(self, cfg):
        path = Path(self.tmp) / 'targets.json'
        path.write_text(json.dumps(cfg))
        return path

    def test_shipped_config_totals(self):
        cfg = read_config(TARGETS)
        self.assertEqual(cfg['total'], 300)
        self.assertEqual(sum(g['count'] for g in cfg['groups']), 300)
        self.assertEqual(cfg['store_total'], 39)
        self.assertEqual(sum(g['count'] for g in cfg['groups'] if g['store']), 39)

    def test_each_plot_size_sums_to_100(self):
        cfg = read_config(TARGETS)
        by_size = {}
        for g in cfg['groups']:
            by_size[(g['width'], g['depth'])] = by_size.get((g['width'], g['depth']), 0) + g['count']
        self.assertEqual(by_size[(20, 50)], 100)
        self.assertEqual(by_size[(30, 40)], 100)
        self.assertEqual(by_size[(30, 50)], 100)

    def test_exact_bhk_mix(self):
        cfg = read_config(TARGETS)
        actual = {(g['width'], g['depth'], g['bedrooms'], g['store']): g['count'] for g in cfg['groups']}
        self.assertEqual(actual, EXPECTED_MIX)

    def test_wrong_total_raises(self):
        with tempfile.TemporaryDirectory() as self.tmp:
            cfg = json.loads(TARGETS.read_text())
            cfg['total'] = 299
            with self.assertRaises(ValueError):
                read_config(self._write(cfg))

    def test_wrong_store_count_raises(self):
        with tempfile.TemporaryDirectory() as self.tmp:
            cfg = json.loads(TARGETS.read_text())
            cfg['store_total'] = 40
            with self.assertRaises(ValueError):
                read_config(self._write(cfg))

    def test_duplicate_group_key_raises(self):
        with tempfile.TemporaryDirectory() as self.tmp:
            cfg = json.loads(TARGETS.read_text())
            # Duplicate an existing (width, depth, bedrooms, store) spec key.
            first = dict(cfg['groups'][0])
            cfg['groups'].append(dict(first))
            # Keep the total consistent so the duplicate check is what trips.
            cfg['groups'][0]['count'] = 0
            with self.assertRaises(ValueError):
                read_config(self._write(cfg))


if __name__ == '__main__':
    unittest.main()
