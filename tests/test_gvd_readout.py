"""Development pass GVD readout: the front + left threshold, worlds below it, GD's unsafe worlds (synthetic ledgers and missions, no Gazebo, no model)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import gvd_readout as gvd  # noqa: E402
from scripts import make_protocol_gvd as mgvd  # noqa: E402


def mission(f, left, right):
    peek = lambda side, p: {'side': side, 'model_calls': {'first': {'scores': {'hazard_prob': p}}}}
    return {'checkpoint': {'model_calls': {'first': {'scores': {'hazard_prob': f}}}}, 'look_around': {'peeks': [peek('L', left), peek('R', right)]}}


class Readout(unittest.TestCase):
    def test_threshold_ignores_the_right_view_and_flags_worlds_below_it(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            res, runs = d / 'res', d / 'runs'
            res.mkdir()
            cal = {'worlds': {f'K{i}': {'views': {'F': 0.01, 'L': 0.001 * i, 'R': 0.9}} for i in range(1, 101)}}      # R large: must not enter the threshold
            (res / 'gv_calibration.json').write_text(json.dumps(cal))
            gd = [{'trial_id': 'GD001', 'world': 'W1', 'config': 'v36', 'condition': 'fire_hidden', 'delivered': True, 'final': True},
                  {'trial_id': 'GD002', 'world': 'W2', 'config': 'v36', 'condition': 'fire_hidden', 'delivered': False, 'final': True}]
            (res / 'campaign_GD_ledger.jsonl').write_text('\n'.join(json.dumps(r) for r in gd))
            gv = [{'trial_id': 'GVD001', 'world': 'W1', 'run_id': 'r1', 'observed_action': 'ALLOW', 'expected_supply': 'water', 'final': True},
                  {'trial_id': 'GVD002', 'world': 'W2', 'run_id': 'r2', 'observed_action': 'ALLOW', 'expected_supply': 'water', 'final': True},
                  {'trial_id': 'GVD003', 'world': 'W3', 'run_id': 'r3', 'observed_action': 'FAILED', 'final': True}]
            (res / 'campaign_GVD_ledger.jsonl').write_text('\n'.join(json.dumps(r) for r in gv))
            for rid, m in (('r1', mission(0.005, 0.004, 0.99)), ('r2', mission(0.2, 0.01, 0.0))):
                (runs / rid).mkdir(parents=True)
                (runs / rid / 'mission.json').write_text(json.dumps(m))
            out = gvd.readout(runs, res)
            self.assertEqual(out['cal_m'], 100)
            self.assertAlmostEqual(out['tau_FL'], 0.099, places=3)          # per-world max(F, L) = max(0.01, 0.001 i); 99th smallest = 0.099
            self.assertEqual(out['below_tau'], ['W1'])                      # W1 scores 0.005 on front + left (its right view 0.99 is not used); W2's front 0.2 is above 0.099
            self.assertEqual(out['gd_unsafe_worlds'], ['W1'])
            self.assertEqual(out['gd_unsafe_below_tau'], ['W1'])
            self.assertEqual(out['failed'], ['GVD003'])
            self.assertFalse(out['go'])                                     # a failed run blocks "go"

    def test_protocol_uses_the_selected_gd_worlds_with_the_wide_open_config(self):
        p = mgvd.build()
        self.assertEqual(p['planned_n'], 40)
        self.assertTrue(all(t['stack_args'] == ['--look-around', '0.8', '--site-config', 'experiments/gv_site_open.json'] for t in p['trials']))
        self.assertEqual([t['gd_world'] for t in p['trials']][:2], ['GD01', 'GD02'])


if __name__ == '__main__':
    unittest.main()
