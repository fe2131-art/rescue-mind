"""I-18: the orchestrator hook renders the operator report non-fatally, with no images and without CJK fonts."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rescuemind import operator_report_render as R

R_build = R.build
MISSION = {'run_id': 'abcdef0123456789', 'instruction': '避難所Bに救急箱を', 'intent': {'item': 'medicine'},
           'events': [{'stage': 'shelter_approach', 't_wall_s': 90.0}]}


def make_run(tmp, mission=MISSION):
    d = Path(tmp)
    if mission is not None:
        (d / 'mission.json').write_text(json.dumps(mission, ensure_ascii=False), encoding='utf8')
    (d / 'stack_result.json').write_text(json.dumps({'state': 'COMPLETED'}), encoding='utf8')
    return d


class Hook(unittest.TestCase):
    def test_renders_without_images(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_run(t)
            outcome = {'state': 'COMPLETED'}
            R.generate_for_run(d, outcome)
            self.assertEqual(outcome.get('operator_report'), 'operator_report.png', outcome)
            self.assertNotIn('operator_report_error', outcome)
            self.assertGreater((d / 'operator_report.png').stat().st_size, 1000)
            self.assertTrue((d / 'operator_report.pdf').is_file())

    def test_disabled_flag_skips(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_run(t)
            outcome = {}
            R.generate_for_run(d, outcome, enabled=False)
            self.assertEqual(outcome, {})
            self.assertFalse((d / 'operator_report.png').exists())

    def test_missing_mission_is_non_fatal(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_run(t, mission=None)
            outcome = {}
            R.generate_for_run(d, outcome)
            self.assertIn('FileNotFoundError', outcome['operator_report_error'])
            self.assertNotIn('operator_report', outcome)

    def test_corrupt_mission_is_non_fatal(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_run(t)
            (d / 'mission.json').write_text('{not json', encoding='utf8')
            outcome = {}
            R.generate_for_run(d, outcome)
            self.assertIn('JSONDecodeError', outcome['operator_report_error'])

    def test_missing_fonts_fall_back(self):
        with tempfile.TemporaryDirectory() as t, \
                mock.patch.object(R, 'FONT_R', '/nonexistent/r.ttc'), mock.patch.object(R, 'FONT_B', '/nonexistent/b.ttc'), \
                mock.patch.dict(R._fc, clear=True):
            d = make_run(t)
            outcome = {'state': 'COMPLETED'}
            R.generate_for_run(d, outcome)
            self.assertEqual(outcome.get('operator_report'), 'operator_report.png', outcome)

    def test_report_sees_in_memory_final_state(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_run(t)
            seen = {}
            with mock.patch.object(R, 'build', side_effect=lambda m, r: seen.update(r=r) or R_build(m, r)):
                R.generate_for_run(d, {'state': 'COMPLETED_EXPECTED_DENIAL', 'memory_update': {'n': 1}})
            self.assertEqual(seen['r']['state'], 'COMPLETED_EXPECTED_DENIAL')
            self.assertIn('memory_update', seen['r'])

    def test_orchestrator_wires_hook_and_flag(self):
        src = (Path(__file__).resolve().parents[1] / 'scripts/v32_orchestrate.py').read_text(encoding='utf8')
        self.assertIn('--no-operator-report', src)
        self.assertIn('args.no_operator_report', src)
        self.assertLess(src.index('generate_for_run(log_dir, outcome)'), src.index("(log_dir/'stack_result.json').write_text"))


if __name__ == '__main__':
    unittest.main()
