"""Pure-geometry regression tests for orientation-aware furniture drawing.

These use a recording fake ImageDraw so they run in-sandbox with no Pillow import.
draw_curated_furniture only calls methods on the passed-in draw object, so we can
hand it a fake that captures the coordinates of every primitive and assert purely
on geometry: every drawn element must stay inside its authored footprint (or, for
stairs, inside clear_bounds_ft).
"""
import unittest

from house_plan_generator.curated_furniture import draw_curated_furniture


class RecordingDraw:
    """Fake ImageDraw that records primitive calls and their coordinates."""

    def __init__(self):
        self.lines = []          # list of point-lists [(x,y), ...]
        self.rectangles = []     # list of (x0,y0,x1,y1)
        self.rounded = []        # list of (x0,y0,x1,y1)
        self.ellipses = []       # list of (x0,y0,x1,y1)

    def line(self, points, **kw):
        self.lines.append(list(points))

    def rectangle(self, xy, **kw):
        self.rectangles.append(tuple(xy))

    def rounded_rectangle(self, xy, **kw):
        self.rounded.append(tuple(xy))

    def ellipse(self, xy, **kw):
        self.ellipses.append(tuple(xy))


# Origin/scale used for every test; identity origin, 10 px per foot keeps math simple.
OX, OY, SCALE = 0, 0, 10
TOL = 1e-6


def footprint_px(f):
    x, y, w, d = f['x_ft'], f['y_ft'], f['width_ft'], f['depth_ft']
    return (OX + x * SCALE, OY + y * SCALE, OX + (x + w) * SCALE, OY + (y + d) * SCALE)


def within(bbox, outer):
    return (bbox[0] >= outer[0] - TOL and bbox[1] >= outer[1] - TOL
            and bbox[2] <= outer[2] + TOL and bbox[3] <= outer[3] + TOL)


def points_within(points, outer):
    return all(outer[0] - TOL <= px <= outer[2] + TOL and outer[1] - TOL <= py <= outer[3] + TOL
               for px, py in points)


def bbox_of_points(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def furn(kind, x, y, w, d, **kw):
    return dict(id='t', room_id='r', kind=kind, x_ft=x, y_ft=y, width_ft=w, depth_ft=d, **kw)


def run(furniture, stairs=None):
    plan = {'furniture': furniture}
    if stairs is not None:
        plan['stairs'] = stairs
    draw = RecordingDraw()
    draw_curated_furniture(draw, plan, OX, OY, SCALE)
    return draw


def all_shapes(draw):
    return draw.rectangles + draw.rounded + draw.ellipses


class BedOrientationTests(unittest.TestCase):
    def _assert_bed_inside(self, head, w=5, d=6.5):
        bed = furn('bed', 2.0, 3.0, w, d, head=head)
        draw = run([bed])
        fp = footprint_px(bed)
        # The outer rounded_rectangle is the footprint itself; every OTHER shape
        # (headboard slab + pillows) must stay inside it.
        self.assertGreaterEqual(len(draw.rounded), 2, 'expected headboard footprint + pillows')
        for shape in draw.rectangles + draw.rounded + draw.ellipses:
            self.assertTrue(within(shape, fp), f'{head} bed shape {shape} escaped footprint {fp}')
        # The body/foot line must also stay inside the footprint.
        for pts in draw.lines:
            self.assertTrue(points_within(pts, fp), f'{head} bed line {pts} escaped footprint {fp}')

    def test_double_bed_all_four_heads_inside_footprint(self):
        for head in ('north', 'south', 'east', 'west'):
            self._assert_bed_inside(head)

    def test_single_bed_all_four_heads_inside_footprint(self):
        for head in ('north', 'south', 'east', 'west'):
            self._assert_bed_inside(head, w=3.5, d=6.5)

    def test_unknown_head_defaults_to_south_and_stays_inside(self):
        self._assert_bed_inside('unspecified')

    def test_headboard_hugs_the_named_wall(self):
        # North headboard slab must sit against the top edge; south against the bottom.
        north = furn('bed', 0, 0, 5, 6.5, head='north')
        dn = run([north])
        # First rectangle after the footprint is the headboard slab.
        slab = dn.rectangles[0]
        self.assertAlmostEqual(slab[1], 0.0, msg='north headboard should touch the top wall')
        south = furn('bed', 0, 0, 5, 6.5, head='south')
        ds = run([south])
        slab = ds.rectangles[0]
        self.assertAlmostEqual(slab[3], 6.5 * SCALE, msg='south headboard should touch the bottom wall')
        west = furn('bed', 0, 0, 6.5, 5, head='west')
        dw = run([west])
        slab = dw.rectangles[0]
        self.assertAlmostEqual(slab[0], 0.0, msg='west headboard should touch the left wall')
        east = furn('bed', 0, 0, 6.5, 5, head='east')
        de = run([east])
        slab = de.rectangles[0]
        self.assertAlmostEqual(slab[2], 6.5 * SCALE, msg='east headboard should touch the right wall')


class SofaOrientationTests(unittest.TestCase):
    def test_wide_sofa_cushions_run_along_width(self):
        sofa = furn('sofa', 0, 0, 6.2, 2.8)  # wide (horizontal) sofa
        draw = run([sofa])
        cushions = draw.rounded[1:]  # rounded[0] is the outer footprint; rest are cushions
        self.assertEqual(len(cushions), 3)
        fp = footprint_px(sofa)
        for c in cushions:
            self.assertTrue(within(c, fp))
        # Cushion centers should be ordered along X (the long axis), not Y.
        xs = sorted((c[0] + c[2]) / 2 for c in cushions)
        ys = [(c[1] + c[3]) / 2 for c in cushions]
        self.assertGreater(xs[-1] - xs[0], SCALE, 'wide sofa cushions should spread along X')
        self.assertLess(max(ys) - min(ys), TOL + 1, 'wide sofa cushion centers should share a row')

    def test_tall_sofa_cushions_run_along_depth(self):
        sofa = furn('sofa', 0, 0, 2.8, 6.2)  # tall (vertical) sofa
        draw = run([sofa])
        cushions = draw.rounded[1:]  # rounded[0] is the outer footprint; rest are cushions
        self.assertEqual(len(cushions), 3)
        fp = footprint_px(sofa)
        for c in cushions:
            self.assertTrue(within(c, fp))
        ys = sorted((c[1] + c[3]) / 2 for c in cushions)
        xs = [(c[0] + c[2]) / 2 for c in cushions]
        self.assertGreater(ys[-1] - ys[0], SCALE, 'tall sofa cushions should spread along Y')
        self.assertLess(max(xs) - min(xs), TOL + 1, 'tall sofa cushion centers should share a column')


class WcRotationTests(unittest.TestCase):
    def test_wc_treatment_differs_by_rotation_but_stays_inside(self):
        signatures = []
        for rot in range(4):
            wc = furn('wc', 1.0, 1.0, 1.6, 2.4, rotation=rot)
            draw = run([wc])
            fp = footprint_px(wc)
            # The tank rectangle + bowl ellipse must both be inside the footprint.
            self.assertTrue(draw.rectangles, 'wc should draw a tank rectangle')
            self.assertTrue(draw.ellipses, 'wc should draw a bowl ellipse')
            for shape in draw.rectangles + draw.ellipses:
                self.assertTrue(within(shape, fp), f'rot={rot} wc shape {shape} escaped {fp}')
            # Signature = tank rectangle position; must differ across the four turns.
            signatures.append(tuple(round(v, 4) for v in draw.rectangles[0]))
        self.assertEqual(len(set(signatures)), 4, 'each quarter-turn should place the tank differently')


class ShelfTests(unittest.TestCase):
    def test_shelf_lines_stay_within_footprint(self):
        shelf = furn('shelves', 0, 0, 6, 1.25)
        draw = run([shelf])
        fp = footprint_px(shelf)
        self.assertTrue(draw.lines, 'shelves should draw shelf lines')
        for pts in draw.lines:
            self.assertTrue(points_within(pts, fp), f'shelf line {pts} escaped {fp}')

    def test_tall_shelf_lines_stay_within_footprint(self):
        shelf = furn('shelves', 0, 0, 1.25, 6)
        draw = run([shelf])
        fp = footprint_px(shelf)
        self.assertTrue(draw.lines)
        for pts in draw.lines:
            self.assertTrue(points_within(pts, fp))


class CounterTests(unittest.TestCase):
    def test_short_rotated_counter_sink_stays_inside(self):
        counter = furn('counter', 5.0, 5.0, 2.0, 2.35)  # short (w<=d), matches C02 counter_e
        draw = run([counter])
        fp = footprint_px(counter)
        # rounded[0] is the footprint, rounded[1] is the sink basin.
        self.assertEqual(len(draw.rounded), 2)
        self.assertTrue(within(draw.rounded[1], fp), 'short counter sink escaped footprint')

    def test_long_counter_hob_symbols_stay_inside(self):
        counter = furn('counter', 0, 0, 6.0, 2.0)  # long horizontal counter
        draw = run([counter])
        fp = footprint_px(counter)
        self.assertTrue(draw.ellipses, 'long counter should draw hob burners')
        for e in draw.ellipses:
            self.assertTrue(within(e, fp), f'hob symbol {e} escaped footprint {fp}')

    def test_narrow_short_counter_symbols_stay_inside(self):
        counter = furn('counter', 0, 0, 1.5, 2.0)  # narrow short counter
        draw = run([counter])
        fp = footprint_px(counter)
        for shape in draw.rounded[1:] + draw.ellipses:
            self.assertTrue(within(shape, fp), f'narrow counter symbol {shape} escaped {fp}')


class StairTests(unittest.TestCase):
    def test_horizontal_reverse_stair_stays_within_clear_bounds(self):
        # A horizontal + reverse dogleg with 3 ft flights inside a 12x6 clear region.
        stair = dict(layout='dogleg', orientation='horizontal', reverse=True,
                     riser_count=16, going_ft=10 / 12, flight_width_ft=3, landing_ft=3,
                     clear_bounds_ft=[4, 8, 16, 14])
        draw = run([], stairs=[stair])
        bounds = (4 * SCALE, 8 * SCALE, 16 * SCALE, 14 * SCALE)
        self.assertTrue(draw.lines, 'oriented stair should draw treads/rails/arrows')
        for pts in draw.lines:
            self.assertTrue(points_within(pts, bounds),
                            f'oriented stair line {pts} escaped clear bounds {bounds}')
        # The landing rectangle must also sit within clear bounds.
        self.assertTrue(draw.rectangles, 'oriented stair should draw a landing rectangle')
        for r in draw.rectangles:
            self.assertTrue(within(r, bounds), f'landing {r} escaped clear bounds {bounds}')

    def test_horizontal_forward_stair_stays_within_clear_bounds(self):
        stair = dict(layout='dogleg', orientation='horizontal', reverse=False,
                     riser_count=16, going_ft=10 / 12, flight_width_ft=3, landing_ft=3,
                     clear_bounds_ft=[4, 8, 16, 14])
        draw = run([], stairs=[stair])
        bounds = (4 * SCALE, 8 * SCALE, 16 * SCALE, 14 * SCALE)
        for pts in draw.lines:
            self.assertTrue(points_within(pts, bounds))

    def test_vertical_reverse_stair_stays_within_clear_bounds(self):
        stair = dict(layout='dogleg', orientation='vertical', reverse=True,
                     riser_count=16, going_ft=10 / 12, flight_width_ft=3, landing_ft=3,
                     clear_bounds_ft=[2, 2, 8, 16])
        draw = run([], stairs=[stair])
        bounds = (2 * SCALE, 2 * SCALE, 8 * SCALE, 16 * SCALE)
        for pts in draw.lines:
            self.assertTrue(points_within(pts, bounds))

    def test_legacy_vertical_stair_still_draws_flights(self):
        # C01-style legacy fields: no orientation/clear_bounds -> old dogleg drawing.
        stair = dict(layout='dogleg', riser_count=16, going_ft=0.8333333333333334,
                     flight_width_ft=3, flight_x_ft=[0.75, 4.5], flight_y_ft=19.5)
        draw = run([], stairs=[stair])
        # Each flight draws riser_count//2 treads + 2 rails + 1 arrow shaft + 1 arrow head.
        # Two flights => at least 2 * (8 + 2) = 20 lines.
        self.assertGreaterEqual(len(draw.lines), 20,
                                'legacy stair should still draw both flights of treads and rails')
        # And it must not draw the oriented landing rectangle.
        self.assertEqual(draw.rectangles, [], 'legacy stair should not draw an oriented landing box')

    def test_undersized_clear_bounds_clamps_and_nothing_escapes(self):
        # A deliberately undersized clear region: landing(3) + run for 8 gaps at
        # going 10/12 would need 3 + 8*0.833 = ~9.67 ft along the run axis, but the
        # region only spans 5 ft. Every primitive must still stay strictly inside
        # clear_bounds_ft thanks to the fail-closed clamp.
        stair = dict(layout='dogleg', orientation='horizontal', reverse=False,
                     riser_count=16, going_ft=10 / 12, flight_width_ft=2, landing_ft=3,
                     clear_bounds_ft=[4, 8, 9, 12])
        draw = run([], stairs=[stair])
        bounds = (4 * SCALE, 8 * SCALE, 9 * SCALE, 12 * SCALE)
        self.assertTrue(draw.lines, 'clamped stair should still draw treads/rails/arrows')
        for pts in draw.lines:
            self.assertTrue(points_within(pts, bounds),
                            f'clamped stair line {pts} escaped clear bounds {bounds}')
        self.assertTrue(draw.rectangles, 'clamped stair should still draw a landing rectangle')
        for r in draw.rectangles:
            self.assertTrue(within(r, bounds), f'clamped landing {r} escaped clear bounds {bounds}')

    def test_undersized_clear_bounds_reverse_and_vertical(self):
        # Same undersized-region guarantee for reverse and vertical orientations.
        for orient, reverse, cb in (
            ('horizontal', True, [4, 8, 9, 12]),
            ('vertical', True, [2, 2, 5, 7]),
            ('vertical', False, [2, 2, 5, 7]),
        ):
            stair = dict(layout='dogleg', orientation=orient, reverse=reverse,
                         riser_count=16, going_ft=10 / 12, flight_width_ft=1.5, landing_ft=3,
                         clear_bounds_ft=cb)
            draw = run([], stairs=[stair])
            bounds = (cb[0] * SCALE, cb[1] * SCALE, cb[2] * SCALE, cb[3] * SCALE)
            for pts in draw.lines:
                self.assertTrue(points_within(pts, bounds),
                                f'{orient} reverse={reverse} line {pts} escaped {bounds}')
            for r in draw.rectangles:
                self.assertTrue(within(r, bounds),
                                f'{orient} reverse={reverse} landing {r} escaped {bounds}')

    def test_legacy_and_oriented_stairs_differ(self):
        legacy = run([], stairs=[dict(layout='dogleg', riser_count=16, going_ft=0.8333,
                                      flight_width_ft=3, flight_x_ft=[0.75, 4.5], flight_y_ft=19.5)])
        oriented = run([], stairs=[dict(layout='dogleg', orientation='horizontal', reverse=False,
                                        riser_count=16, going_ft=10 / 12, flight_width_ft=3,
                                        landing_ft=3, clear_bounds_ft=[4, 8, 16, 14])])
        self.assertEqual(legacy.rectangles, [])
        self.assertTrue(oriented.rectangles)


if __name__ == '__main__':
    unittest.main()
