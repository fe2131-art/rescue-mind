"""Study GD Amendment 1: the depot calibration from fire-free missions with the threshold off (synthetic runs, no model)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import gd_calibrate as gdc  # noqa: E402
from scripts import make_protocol_gd as mgd  # noqa: E402


def mission(front, left, right):
    mc = lambda p: {'first': {'scores': {'hazard_prob': p}}}
    return {'checkpoint': {'model_calls': mc(front)}, 'look_around': {'peeks': [{'side': 'L', 'model_calls': mc(left)}, {'side': 'R', 'model_calls': mc(right)}]}}


def build(scores, tmp):
    rows = []
    for i, (f, l, r) in enumerate(scores):
        tid = f'GDK{i + 1:03d}'
        (tmp / tid).mkdir()
        (tmp / tid / 'mission.json').write_text(json.dumps(mission(f, l, r)))
        rows.append({'trial_id': tid, 'run_id': tid, 'observed_action': 'ALLOW', 'final': True, 'expected_supply': 'water'})
    return rows


class Calibrate(unittest.TestCase):
    def test_rank_rule_over_the_per_world_maximum_and_rounding_up(self):
        tmp = Path(tempfile.mkdtemp())
        scores = [(0.001 * (i % 7 + 1), 0.002, 0.003) for i in range(98)] + [(0.0, 0.0, 0.0213), (0.0, 0.0, 0.0301)]
        out = gdc.calibrate(build(scores, tmp), tmp)
        self.assertEqual(out['m'], 100)
        self.assertAlmostEqual(out['tau_raw'], 0.0213)                  # m = 100, alpha = 2%: the 99th smallest = the second largest
        self.assertEqual(out['tau_cal'], 0.022)                         # rounded up to the next thousandth
        self.assertFalse(out['stop'])
        self.assertAlmostEqual(out['guaranteed_false_stop_bound'], 0.0198, places=3)

    def test_stop_rule_when_the_threshold_is_not_below_the_default(self):
        tmp = Path(tempfile.mkdtemp())
        scores = [(0.002, 0.003, 0.004)] * 97 + [(0.0, 0.0, 0.133)] * 3
        out = gdc.calibrate(build(scores, tmp), tmp)
        self.assertTrue(out['stop'])
        self.assertGreaterEqual(out['tau_cal'], 0.05)

    def test_failed_and_incomplete_runs_are_excluded(self):
        tmp = Path(tempfile.mkdtemp())
        rows = build([(0.001, 0.002, 0.003)] * 95, tmp)
        rows[0]['observed_action'] = 'FAILED'
        (tmp / 'GDK002' / 'mission.json').write_text(json.dumps({'checkpoint': {'model_calls': {'first': {'scores': {'hazard_prob': 0.1}}}}}))   # no peeks: the look-around did not run
        out = gdc.calibrate(rows, tmp)
        self.assertEqual(sorted(out['failed_or_incomplete']), ['GDK001', 'GDK002'])
        self.assertEqual(out['m'], 93)
        self.assertFalse(out['stop'])                                    # 93 usable worlds are enough and every score is far below 0.05
        self.assertAlmostEqual(out['tau_raw'], 0.003)

    def test_fewer_than_ninety_usable_worlds_stops_the_calibration(self):
        tmp = Path(tempfile.mkdtemp())
        out = gdc.calibrate(build([(0.001, 0.002, 0.003)] * 80, tmp), tmp)
        self.assertTrue(out['stop'])
        self.assertIsNone(out['tau_cal'])

    def test_calibration_protocol_is_fire_free_threshold_off_and_apart_from_the_study(self):
        p = mgd.calibration_protocol()
        self.assertEqual(p['planned_n'], 100)
        self.assertTrue(all(t['condition'] == 'plain' and t['stack_args'] == mgd.CONFIG_OPEN for t in p['trials']))
        gd_worlds = {w['world'] for w in mgd.plain_worlds() + mgd.fire_candidates()}
        self.assertTrue(gd_worlds.isdisjoint({t['world'] for t in p['trials']}))
        cfg = json.loads((ROOT / 'experiments/gd_site_open.json').read_text())
        self.assertEqual(cfg['hazard_threshold'], 1.0)


if __name__ == '__main__':
    unittest.main()
