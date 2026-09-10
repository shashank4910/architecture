"""Fail-closed release-gate checks using the curated C01 concept and mutations.

validate_catalog_plan pulls in concept_review + validator + bulk_furnishing,
none of which require numpy/PIL/ortools, so this suite runs in-sandbox.
"""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from house_plan_generator.catalog_validation import validate_catalog_plan

C01 = Path(__file__).resolve().parents[1] / 'plans/curated/C01_north_20x50_2bhk.json'


class CatalogValidationTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(C01.read_text())

    def assert_fail(self, mutate):
        plan = deepcopy(self.plan)
        mutate(plan)
        result = validate_catalog_plan(plan)
        self.assertEqual(result['overall'], 'FAIL', result.get('errors'))
        return result

    def test_unmutated_curated_concept_passes(self):
        result = validate_catalog_plan(self.plan)
        self.assertEqual(result['overall'], 'PASS', result['errors'])
        self.assertFalse(result['production_ready'])

    def test_wrong_declared_bhk_fails(self):
        r = self.assert_fail(lambda p: p.update(bedrooms=3))
        self.assertTrue(any('BHK' in e or 'bedroom' in e.lower() for e in r['errors']))

    def test_store_label_without_shelving_fails(self):
        # Relabel the kitchen as a store: it has no shelving furniture.
        def mutate(p):
            room = next(r for r in p['rooms'] if r['id'] == 'kitchen')
            room['kind'] = 'store'
            room['name'] = 'Store'
        r = self.assert_fail(mutate)
        self.assertTrue(any('store' in e.lower() or 'shelves' in e.lower() or 'furniture' in e.lower() for e in r['errors']))

    def test_undersized_store_fails(self):
        # Convert the passage into a tiny "store": below the 5 ft / 25 sqft rule.
        def mutate(p):
            room = next(r for r in p['rooms'] if r['id'] == 'hall')
            room['kind'] = 'store'
            room['name'] = 'Store'
            p['furniture'].append({'id': 'st_shelf', 'room_id': 'hall', 'kind': 'shelves', 'x_ft': room['x_ft'], 'y_ft': room['y_ft'], 'width_ft': 1, 'depth_ft': 1})
        r = self.assert_fail(mutate)
        self.assertTrue(any('store' in e.lower() or 'usable' in e.lower() for e in r['errors']))

    def test_interior_bathroom_without_window_or_exhaust_fails(self):
        def mutate(p):
            p['windows'] = [w for w in p['windows'] if w['room_id'] != 'bath1']
            room = next(r for r in p['rooms'] if r['id'] == 'bath1')
            room.pop('ventilation', None)
        r = self.assert_fail(mutate)
        self.assertTrue(any('ventilation' in e.lower() for e in r['errors']))

    def test_non_finite_geometry_fails(self):
        r = self.assert_fail(lambda p: p['rooms'][0].update(x_ft=float('nan')))
        self.assertTrue(any('finite' in e.lower() or 'numeric' in e.lower() for e in r['errors']))

    def test_infinite_geometry_fails(self):
        self.assert_fail(lambda p: p['rooms'][0].update(width_ft=float('inf')))

    def test_furniture_blocks_opening_approach_fails(self):
        # Move the master bed onto its own door swing envelope.
        def mutate(p):
            bed = next(f for f in p['furniture'] if f['id'] == 'master_bed')
            bed.update(x_ft=7.4, y_ft=39.5)
        r = self.assert_fail(mutate)
        self.assertTrue(any('swing' in e.lower() or 'approach' in e.lower() or 'opening' in e.lower() for e in r['errors']))

    def test_bedroom_through_bedroom_with_misleading_ensuite_fails(self):
        # Add a bedroom-to-bedroom door and dress it with misleading ensuite metadata.
        def mutate(p):
            bed2 = next(r for r in p['rooms'] if r['id'] == 'bed2')
            bed2['ensuite_of'] = 'master'
            p['doors'].append({
                'id': 'master_bed2_private', 'room_id': 'master', 'side': 'east',
                'offset_ft': 5, 'width_ft': 3, 'connects_to': 'bed2', 'opening_type': 'swing', 'ensuite': True,
            })
        r = self.assert_fail(mutate)
        self.assertTrue(any('bedroom-to-bedroom' in e or 'private' in e.lower() for e in r['errors']))

    def test_common_bathroom_through_bedroom_fails(self):
        # Remove the bathroom's common-side door and attach it only to a bedroom.
        def mutate(p):
            p['doors'] = [d for d in p['doors'] if d['id'] != 'bath_entry']
            p['doors'].append({
                'id': 'bed2_bath_private', 'room_id': 'bed2', 'side': 'west',
                'offset_ft': 1, 'width_ft': 2.75, 'connects_to': 'bath1', 'opening_type': 'swing',
            })
        r = self.assert_fail(mutate)
        self.assertTrue(r['errors'])

    def test_door_outside_shared_segment_fails(self):
        # Shrink the dining target so the living-dining door no longer lies on the shared wall.
        def mutate(p):
            target = next(r for r in p['rooms'] if r['id'] == 'dining')
            target.update(x_ft=14, width_ft=6)
        r = self.assert_fail(mutate)
        self.assertTrue(any('shared wall' in e for e in r['errors']))


if __name__ == '__main__':
    unittest.main()
