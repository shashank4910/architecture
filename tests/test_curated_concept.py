from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from house_plan_generator.concept_review import review_concept
from house_plan_generator.renderer_2d import render_2d
from house_plan_generator.validator import _is_ensuite_connection, _room_has_private_safe_access, _room_category
from house_plan_generator.openings import door_swing
from house_plan_generator.curated_furniture import draw_curated_furniture
from unittest.mock import Mock

PLAN=Path(__file__).resolve().parents[1]/'plans/curated/C01_north_20x50_2bhk.json'

class CuratedConceptTests(unittest.TestCase):
    def setUp(self):self.plan=json.loads(PLAN.read_text())

    def test_authored_concept_and_routes(self):
        r=review_concept(self.plan)
        self.assertEqual(r['errors'],[])
        self.assertEqual(r['entrance_routes']['master'],['exterior','living','dining','hall','corridor','master'])
        self.assertEqual(r['estimated_clear_dimensions']['hall']['width_ft'],3.5)

    def test_partial_shared_wall_rejects_door_outside_target(self):
        d=next(d for d in self.plan['doors'] if d['id']=='living_dining')
        # Target still touches source, but no longer across the opening.
        target=next(r for r in self.plan['rooms'] if r['id']=='dining')
        target.update(x_ft=14,width_ft=6)
        self.assertTrue(any('actual shared wall' in e for e in review_concept(self.plan)['errors']))

    def test_bedroom_metadata_cannot_bypass_privacy(self):
        a=dict(id='master',name='Master bedroom',kind='habitable')
        b=dict(id='bed2',name='Bedroom 2',kind='habitable',ensuite_of='master')
        self.assertFalse(_is_ensuite_connection({'ensuite':True},a,b))
        b.update(kind='bathroom',name='Ensuite',id='bath2')
        self.assertTrue(_is_ensuite_connection({'ensuite':True},a,b))

    def test_common_room_behind_bedroom_not_an_access_origin(self):
        graph={'exterior':{'master'},'master':{'exterior','dining'},'dining':{'master','bed2'},'bed2':{'dining'}}
        self.assertFalse(_room_has_private_safe_access(graph,'bed2',{'master','bed2'},{'dining'}))

    def test_bedroom_lobby_is_circulation(self):
        self.assertEqual(_room_category({'id':'lobby','name':'Bedroom lobby','kind':'circulation'}),'common')

    def test_furniture_cannot_block_door(self):
        next(f for f in self.plan['furniture'] if f['id']=='master_bed').update(x_ft=7.4,y_ft=39.5)
        self.assertTrue(any('swing envelope' in e for e in review_concept(self.plan)['errors']))

    def test_wardrobe_use_space_must_be_free(self):
        next(f for f in self.plan['furniture'] if f['id']=='bed2_bed')['y_ft']=42
        self.assertTrue(any('use clearance' in e for e in review_concept(self.plan)['errors']))

    def test_stair_landings_count_toward_fit(self):
        self.plan['stairs'][0]['going_ft']=2
        self.assertTrue(any('landings do not fit' in e for e in review_concept(self.plan)['errors']))

    def test_renderer_preserves_explicit_door_and_furniture(self):
        with tempfile.TemporaryDirectory() as d:
            original=deepcopy(self.plan)
            m=render_2d(self.plan,Path(d)/'plan.png')
            self.assertEqual(original,self.plan)
            self.assertEqual(m['furniture'],self.plan['furniture'])
            for door in m['doors']:
                self.assertEqual(door['rendered_interval_ft'],[door['offset_ft'],door['offset_ft']+door['width_ft']])


class SecondConceptTests(unittest.TestCase):
    def setUp(self):
        self.plan=json.loads(PLAN.with_name('C02_north_20x50_2bhk.json').read_text())

    def test_second_concept_double_rooms_and_shorter_circulation(self):
        report=review_concept(self.plan)
        self.assertEqual(report['errors'],[])
        self.assertEqual(report['circulation_cell_area_sqft'],101.5)
        for rid in ('master','bed2'):
            self.assertEqual(report['estimated_clear_dimensions'][rid],{'width_ft':9.0,'depth_ft':13.0})
            bed=next(f for f in self.plan['furniture'] if f['room_id']==rid and f['kind']=='bed')
            self.assertEqual((bed['width_ft'],bed['depth_ft']),(5,6.5))
            self.assertEqual(report['entrance_routes'][rid],['exterior','foyer','living','hall',rid])
        self.assertEqual(report['entrance_routes']['staircase'],['exterior','foyer','staircase'])

    def test_entry_leaf_is_on_parking_side_away_from_stair_opening(self):
        room=next(r for r in self.plan['rooms'] if r['id']=='foyer')
        door=next(d for d in self.plan['doors'] if d['id']=='entrance')
        swing=door_swing(room,door,self.plan)
        self.assertEqual(swing['hinge_ft'],(10.75,0))
        self.assertEqual(swing['leaf_ft'],(10.75,3))
        self.assertEqual(swing['arc_degrees'],(90,180))
        with tempfile.TemporaryDirectory() as d:
            manifest=render_2d(self.plan,Path(d)/'c02.png')
        self.assertEqual(next(d for d in manifest['doors'] if d['id']=='entrance')['hinge'],'end')

    def test_short_counter_sink_symbol_stays_inside_counter(self):
        counter=next(f for f in self.plan['furniture'] if f['id']=='counter_e')
        draw=Mock()
        draw_curated_furniture(draw,{'furniture':[counter]},0,0,28)
        rectangles=[call.args[0] for call in draw.rounded_rectangle.call_args_list]
        self.assertEqual(len(rectangles),2)
        outer,inner=rectangles
        self.assertGreaterEqual(inner[0],outer[0]);self.assertGreaterEqual(inner[1],outer[1])
        self.assertLessEqual(inner[2],outer[2]);self.assertLessEqual(inner[3],outer[3])

    def test_bedside_clearance_obstruction_is_rejected(self):
        bed=next(f for f in self.plan['furniture'] if f['id']=='bed2_bed')
        bed['x_ft']+=.5
        self.assertTrue(any('bed2_east_bedside: use clearance obstructed' in e for e in review_concept(self.plan)['errors']))

if __name__=='__main__':unittest.main()
