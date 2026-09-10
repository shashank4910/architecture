"""Orchestration + render-gate fail-closed checks with solver/renderer mocked.

Everything here isolates ortools (solve_layout/assemble_layout), numpy
(DiversityIndex) and Pillow (render_2d) behind mocks/patches so the quota,
resume, shortfall-report and render-gate logic runs in-sandbox.
"""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from house_plan_generator import catalog as C
from house_plan_generator import catalog_outputs as CO


def tiny_config(tmp):
    """A 2-plan / 2-group config so an underfill run is cheap."""
    cfg = {
        'version': 2, 'total': 2, 'store_total': 0, 'facing': 'north',
        'near_duplicate_threshold': 0.88, 'max_per_layout_family': 8,
        'groups': [
            {'width': 20, 'depth': 50, 'bedrooms': 2, 'store': False, 'count': 1},
            {'width': 30, 'depth': 40, 'bedrooms': 3, 'store': False, 'count': 1},
        ],
    }
    path = Path(tmp) / 'targets.json'
    path.write_text(json.dumps(cfg))
    return path


def make_plan(width, depth, bedrooms, store=False, design_id='plan'):
    """A minimal canonical-ish plan good enough for group_key + fake validation."""
    return {
        'design_id': design_id,
        'plot': {'width_ft': width, 'depth_ft': depth, 'facing': 'north'},
        'bedrooms': bedrooms,
        'rooms': [
            {'id': 'living', 'kind': 'habitable', 'name': 'Living', 'x_ft': 0, 'y_ft': 0, 'width_ft': width, 'depth_ft': 20},
            {'id': 'master', 'kind': 'habitable', 'name': 'Master bedroom', 'x_ft': 0, 'y_ft': 20, 'width_ft': width, 'depth_ft': depth - 20},
        ],
        'doors': [{'id': 'd1', 'room_id': 'living', 'connects_to': 'master', 'side': 'south', 'offset_ft': 1, 'width_ft': 3}],
    }


class FakeIndex:
    """Accept-everything diversity stand-in so numpy is never needed."""
    def __init__(self, *a, **k):
        self.threshold = 0.88
        self.family_limit = 8
        self.families = {}

    def check(self, plan):
        return None, 0.0

    def add(self, plan):
        return 0.0


def passing_validation(plan):
    return {'overall': 'PASS', 'errors': [], 'production_ready': False}


def _load_cli():
    import importlib.util
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'generate_300_2d_batch.py'
    spec = importlib.util.spec_from_file_location('generate_300_2d_batch', script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CliArgumentTests(unittest.TestCase):
    def test_non_positive_preview_rejected_before_search(self):
        cli = _load_cli()
        with patch.object(cli, 'generate_catalog') as gen:
            with self.assertRaises(SystemExit):
                cli.main(['--preview', '0'])
            gen.assert_not_called()

    def test_preview_and_render_mutually_exclusive(self):
        cli = _load_cli()
        with patch.object(cli, 'generate_catalog') as gen:
            with self.assertRaises(SystemExit):
                cli.main(['--preview', '3', '--render'])
            gen.assert_not_called()

    def test_incomplete_status_returns_exit_code_2(self):
        cli = _load_cli()
        summary = {'status': 'INCOMPLETE', 'requested': 300, 'accepted': 0}
        with patch.object(cli, 'generate_catalog', return_value={'summary': summary, 'plans': [], 'root': 'x'}), \
             patch.object(cli, 'write_catalog_outputs') as wco:
            code = cli.main(['--max-attempts', '0'])
            self.assertEqual(code, 2)
            wco.assert_not_called()

    def test_positive_preview_on_incomplete_still_returns_2(self):
        cli = _load_cli()
        summary = {'status': 'INCOMPLETE', 'requested': 300, 'accepted': 1}
        with patch.object(cli, 'generate_catalog', return_value={'summary': summary, 'plans': [], 'root': 'x'}), \
             patch.object(cli, 'write_catalog_outputs', return_value={'rendered': 1}):
            code = cli.main(['--max-attempts', '0', '--preview', '1'])
            self.assertEqual(code, 2)


class UnderfillReportTests(unittest.TestCase):
    def test_bounded_underfill_is_incomplete_with_exact_shortfall(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = tiny_config(tmp)
            root = Path(tmp) / 'out'
            # Solver yields nothing; no structural seeds match this tiny config's groups.
            with patch.object(C, 'assemble_layout', return_value=(None, 'infeasible')), \
                 patch.object(C, 'solve_layout', return_value={'status': 'UNKNOWN'}):
                result = C.generate_catalog(requested=2, root=root, max_attempts=4, seconds=1, workers=1, config_path=cfg_path)
            summary = result['summary']
            self.assertEqual(summary['status'], 'INCOMPLETE')
            self.assertEqual(summary['accepted'], 0)
            shortfalls = {(g['width'], g['depth'], g['bedrooms'], g['store']): g['shortfall'] for g in summary['groups']}
            self.assertEqual(shortfalls[(20, 50, 2, False)], 1)
            self.assertEqual(shortfalls[(30, 40, 3, False)], 1)
            report = json.loads((root / 'generation_report.json').read_text())
            self.assertEqual(report['status'], 'INCOMPLETE')
            # Bootstrap (seed) attempts are reported distinctly from solver attempts.
            self.assertIn('bootstrap_attempts', report)
            self.assertIn('solver_attempts', report)
            self.assertEqual(report['solver_attempts'], 4)


class ResumeEvidenceTests(unittest.TestCase):
    def _seed_accepted_bank(self, root, cfg_path):
        """Run once with a fake solver that fills the tiny bank exactly."""
        def fake_assemble(raw, width, depth, bedrooms, store, seed, *a, **k):
            # Only the two tiny-config groups produce a plan; anything else
            # (e.g. structural seeds) is infeasible for this config.
            if (width, depth, bedrooms) in {(20, 50, 2), (30, 40, 3)}:
                return make_plan(width, depth, bedrooms, design_id=f'seed_{width}x{depth}'), None
            return None, 'infeasible'

        with patch.object(C, 'DiversityIndex', FakeIndex), \
             patch.object(C, 'validate_catalog_plan', side_effect=passing_validation), \
             patch.object(C, 'assemble_layout', side_effect=fake_assemble), \
             patch.object(C, 'solve_layout', return_value={'rooms': {}}):
            C.generate_catalog(requested=2, root=root, max_attempts=4, seconds=1, workers=1, config_path=cfg_path)

    def test_resume_preserves_accepted_json_and_review_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = tiny_config(tmp)
            root = Path(tmp) / 'out'
            self._seed_accepted_bank(root, cfg_path)
            plans_dir = root / 'plans'
            files = sorted(p.name for p in plans_dir.glob('*.json'))
            self.assertEqual(len(files), 2)
            # Attach human review evidence to one accepted plan.
            target = plans_dir / files[0]
            data = json.loads(target.read_text())
            data['review'] = {'reviewer': 'human', 'verdict': 'approved-for-preview'}
            target.write_text(json.dumps(data, indent=2) + '\n')
            before = {p.name: p.read_text() for p in plans_dir.glob('*.json')}

            # Resume: no new solver work. Existing accepted JSON must survive.
            with patch.object(C, 'DiversityIndex', FakeIndex), \
                 patch.object(C, 'validate_catalog_plan', side_effect=passing_validation), \
                 patch.object(C, 'assemble_layout', return_value=(None, 'infeasible')), \
                 patch.object(C, 'solve_layout', return_value={'status': 'UNKNOWN'}):
                result = C.generate_catalog(requested=2, root=root, max_attempts=0, seconds=1, workers=1, config_path=cfg_path)

            after_files = sorted(p.name for p in plans_dir.glob('*.json'))
            self.assertEqual(after_files, files, 'resume must not clone or erase accepted JSON')
            reloaded = json.loads(target.read_text())
            self.assertEqual(reloaded.get('review'), {'reviewer': 'human', 'verdict': 'approved-for-preview'},
                             'review evidence for unchanged content must be preserved')
            self.assertEqual(result['summary']['accepted'], 2)

    def test_resume_on_malformed_json_gives_actionable_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = tiny_config(tmp)
            root = Path(tmp) / 'out'
            plans_dir = root / 'plans'
            plans_dir.mkdir(parents=True)
            (plans_dir / 'broken.json').write_text('{ not valid json')
            with patch.object(C, 'DiversityIndex', FakeIndex), \
                 patch.object(C, 'validate_catalog_plan', side_effect=passing_validation), \
                 patch.object(C, 'assemble_layout', return_value=(None, 'x')), \
                 patch.object(C, 'solve_layout', return_value={'status': 'UNKNOWN'}):
                with self.assertRaises(ValueError) as ctx:
                    C.generate_catalog(requested=2, root=root, max_attempts=0, seconds=1, workers=1, config_path=cfg_path)
            msg = str(ctx.exception)
            self.assertIn('broken.json', msg)
            self.assertIn('malformed', msg.lower())


class RenderGateTests(unittest.TestCase):
    def test_full_render_refused_on_incomplete_bank_before_renderer(self):
        render = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(CO, '_load_renderer', return_value=render), \
                 patch.object(CO, '_load_pillow', return_value=(MagicMock(), MagicMock())):
                with self.assertRaises(ValueError):
                    CO.render_catalog(tmp, {'plans': [make_plan(20, 50, 2)], 'summary': {'requested': 300}}, preview=None)
            render.assert_not_called()

    def test_full_render_refused_on_wrong_quota_before_renderer(self):
        render = MagicMock()
        # len(plans) == requested but the per-group quota mix is wrong.
        plans = [make_plan(20, 50, 2, design_id=f'p{n}') for n in range(2)]
        summary = {'requested': 2}
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = tiny_config(tmp)
            with patch.object(CO, '_load_renderer', return_value=render), \
                 patch.object(CO, '_load_pillow', return_value=(MagicMock(), MagicMock())):
                with self.assertRaises(ValueError):
                    CO.render_catalog(tmp, {'plans': plans, 'summary': summary}, preview=None, config_path=cfg_path)
            render.assert_not_called()

    def test_invalid_candidate_refused_before_renderer(self):
        render = MagicMock()
        plans = [make_plan(20, 50, 2)]
        failing = {'overall': 'FAIL', 'errors': ['bad'], 'production_ready': False}
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(CO, '_load_renderer', return_value=render), \
                 patch.object(CO, '_load_pillow', return_value=(MagicMock(), MagicMock())), \
                 patch.object(CO, 'validate_catalog_plan', return_value=failing), \
                 patch.object(CO, 'DiversityIndex', FakeIndex):
                with self.assertRaises(ValueError):
                    CO.render_catalog(tmp, {'plans': plans, 'summary': {'requested': 1}}, preview=1)
            render.assert_not_called()

    def test_generate_and_write_refuses_incomplete_before_renderer(self):
        render = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'out'
            # Use the shipped 300-plan config (so requested matches) but produce
            # nothing: generate_and_write must refuse before any render.
            with patch.object(C, 'DiversityIndex', FakeIndex), \
                 patch.object(C, 'validate_catalog_plan', side_effect=passing_validation), \
                 patch.object(C, 'assemble_layout', return_value=(None, 'infeasible')), \
                 patch.object(C, 'solve_layout', return_value={'status': 'UNKNOWN'}), \
                 patch.object(CO, '_load_renderer', return_value=render):
                with self.assertRaises(RuntimeError):
                    C.generate_and_write_catalog(root=root)
            render.assert_not_called()


class PreviewRenderTests(unittest.TestCase):
    def _fake_pillow(self, files_written):
        image = MagicMock()
        img_instance = MagicMock()
        img_instance.width = 100
        img_instance.__enter__ = lambda s: img_instance
        img_instance.__exit__ = lambda s, *a: False
        img_instance.thumbnail = lambda size: None
        image.new.return_value = img_instance
        image.open.return_value = img_instance
        img_instance.save = lambda p: files_written.append(Path(p))
        draw = MagicMock()
        draw.Draw.return_value = MagicMock()
        return image, draw

    def test_preview_renders_only_requested_count_and_all_in_gallery(self):
        rendered = []
        files_written = []

        def fake_render(plan, path):
            rendered.append(Path(path))
            Path(path).write_bytes(b'PNG')

        plans = [make_plan(20, 50, 2, design_id=f'plan_{n}') for n in range(4)]
        # Distinct geometry so filenames differ.
        for n, p in enumerate(plans):
            p['rooms'][1]['depth_ft'] = 30 - n
        summary = {'requested': 300, 'near_duplicate_threshold': 0.88, 'max_per_layout_family': 8}
        with tempfile.TemporaryDirectory() as tmp:
            image, draw = self._fake_pillow(files_written)
            with patch.object(CO, '_load_renderer', return_value=fake_render), \
                 patch.object(CO, '_load_pillow', return_value=(image, draw)), \
                 patch.object(CO, 'validate_catalog_plan', side_effect=passing_validation), \
                 patch.object(CO, 'DiversityIndex', FakeIndex):
                report = CO.render_catalog(tmp, {'plans': plans, 'summary': summary}, preview=2)
            self.assertEqual(report['rendered'], 2)
            self.assertEqual(len(rendered), 2)
            self.assertEqual(len(report['images']), 2)
            gallery_files = {i['file'] for i in report['images']}
            for path in rendered:
                self.assertIn(path.name, gallery_files)
            self.assertFalse(report['production_ready'])
            self.assertEqual(report['visual_review'], 'pending')

    def test_unchanged_plan_and_renderer_hash_reuses_cached_png(self):
        rendered = []
        files_written = []

        def fake_render(plan, path):
            rendered.append(Path(path))
            Path(path).write_bytes(b'PNG')

        plans = [make_plan(20, 50, 2, design_id='plan_a')]
        summary = {'requested': 300, 'near_duplicate_threshold': 0.88, 'max_per_layout_family': 8}
        with tempfile.TemporaryDirectory() as tmp:
            image, draw = self._fake_pillow(files_written)
            with patch.object(CO, '_load_renderer', return_value=fake_render), \
                 patch.object(CO, '_load_pillow', return_value=(image, draw)), \
                 patch.object(CO, 'validate_catalog_plan', side_effect=passing_validation), \
                 patch.object(CO, 'DiversityIndex', FakeIndex):
                CO.render_catalog(tmp, {'plans': plans, 'summary': summary}, preview=1)
                self.assertEqual(len(rendered), 1)
                # Second call, identical plan + renderer hash: no re-render.
                CO.render_catalog(tmp, {'plans': plans, 'summary': summary}, preview=1)
            self.assertEqual(len(rendered), 1, 'unchanged plan+renderer hash must reuse the cached PNG')


if __name__ == '__main__':
    unittest.main()
