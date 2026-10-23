"""Study JK: protocol (GM's worlds, one new arm), the registered claims on synthetic ledgers, the pilot gate and the run script's guards."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import make_protocol_jk as mjk  # noqa: E402
from scripts import jk_analysis as jk  # noqa: E402


def gm_proto():
    return json.loads((ROOT / 'experiments/campaign_gm_protocol.json').read_text())


class Protocol(unittest.TestCase):
    def test_worlds_arm_and_order(self):
        p = mjk.build(json.loads(mjk.SELECTION.read_text()))
        self.assertEqual(p['planned_n'], 132)
        self.assertEqual({t['condition'] for t in p['trials']}, {'fire_hidden', 'plain'})
        self.assertEqual(sum(t['condition'] == 'fire_hidden' for t in p['trials']), 100)
        self.assertTrue(all(t['stack_args'] == ['--adaptive-views', '0.8'] and t['config'] == 'adapt' for t in p['trials']))
        gm = {t['world']: t['world_spec'] for t in gm_proto()['trials']}
        self.assertTrue(all(t['world_spec'] == gm[t['world']] for t in p['trials']))          # the worlds are GM's, byte for byte
        self.assertEqual(len({t['world'] for t in p['trials']}), 132)

    def test_pilot_forces_the_extras_only_in_the_fire_free_runs(self):
        ts = mjk.pilot_protocol()['trials']
        self.assertEqual([t['config'] for t in ts], ['adapt', 'adapt_forced', 'adapt_forced'])
        self.assertEqual(ts[0]['stack_args'], ['--adaptive-views', '0.8'])
        self.assertIn('--adaptive-tau-sus', ts[1]['stack_args'])
        self.assertEqual([t['condition'] for t in ts], ['fire_hidden', 'plain', 'plain'])

    def test_committed_protocols_match_the_generator(self):
        self.assertEqual(json.loads(mjk.OUT.read_text()), json.loads(json.dumps(mjk.build(json.loads(mjk.SELECTION.read_text())))))
        self.assertEqual(json.loads(mjk.PILOT.read_text()), json.loads(json.dumps(mjk.pilot_protocol())))


class Claims(unittest.TestCase):
    def synthetic(self, adapt_unsafe, adapt_false_stops, v36_unsafe=14):
        jp = json.loads(mjk.OUT.read_text())
        gp = gm_proto()
        sel = json.loads(mjk.SELECTION.read_text())
        fire_ids = [t['world'] for t in jp['trials'] if t['condition'] == 'fire_hidden']
        plain_ids = [t['world'] for t in jp['trials'] if t['condition'] == 'plain']
        bad_a = set(fire_ids[:adapt_unsafe])
        bad_v = set(fire_ids[:v36_unsafe])
        bad_fs = set(plain_ids[:adapt_false_stops])
        row = lambda tid, obs: {'trial_id': tid, 'observed_action': obs, 'mission_time_s': 40.0, 'run_id': None, 'final': True}
        jk_rows = {t['id']: row(t['id'], ('ALLOW' if t['world'] in bad_a else 'DENY_HAZARD') if t['condition'] == 'fire_hidden' else ('DENY_HAZARD' if t['world'] in bad_fs else 'ALLOW')) for t in jp['trials']}
        gm_rows = {}
        for t in gp['trials']:
            if t['config'] == 'v36':
                gm_rows[t['id']] = row(t['id'], ('ALLOW' if t['world'] in bad_v else 'DENY_HAZARD') if t['condition'] == 'fire_hidden' else 'ALLOW')
            elif t['config'] == 'left':
                gm_rows[t['id']] = row(t['id'], 'DENY_HAZARD' if t['condition'] == 'fire_hidden' else 'ALLOW')
        return jk.analyse(jp, jk_rows, gp, gm_rows, sel)

    def test_holding_case(self):
        c = self.synthetic(3, 1)['criteria']
        self.assertTrue(c['JK1_paired_one_sided_p_below_005_and_fewer'] and c['JK2_adapt_upper_at_most_10pct'] and c['JK3_false_stops_at_most_3'])

    def test_budget_line_is_k_at_most_4(self):
        self.assertTrue(self.synthetic(4, 0)['criteria']['JK2_adapt_upper_at_most_10pct'])
        self.assertFalse(self.synthetic(5, 0)['criteria']['JK2_adapt_upper_at_most_10pct'])

    def test_false_stop_line_and_no_gain(self):
        self.assertFalse(self.synthetic(3, 4)['criteria']['JK3_false_stops_at_most_3'])
        self.assertFalse(self.synthetic(14, 0)['criteria']['JK1_paired_one_sided_p_below_005_and_fewer'])       # no difference to v36


class Wiring(unittest.TestCase):
    def test_orchestrator_passes_tau_sus_only_when_given(self):
        import scripts.v32_orchestrate as orch
        kw = dict(mission_timeout=900, evidence_dir=Path('/tmp/abcdef0123456789'), adaptive_views=0.8)
        argv = ' '.join(orch.build_plan('live', '避難所Bに飲料水を届けて', **kw)['mission'].argv)
        self.assertIn('--adaptive-views 0.8', argv)
        self.assertNotIn('--adaptive-tau-sus', argv)                                   # the registered arm keeps the mission's default 0.005
        argv = ' '.join(orch.build_plan('live', '避難所Bに飲料水を届けて', adaptive_tau_sus=0.0, **kw)['mission'].argv)
        self.assertIn('--adaptive-tau-sus 0.0', argv)                                  # the pilot forces the extra views


class Guards(unittest.TestCase):
    def test_run_script_lock_and_guards(self):
        s = (ROOT / 'scripts/jk_run.sh').read_text()
        self.assertIn('flock 9', s)
        for f in ('PREREGISTRATION_JK.md', 'campaign_GM_ledger.jsonl', 'gm_summary.json', 'campaign_gm_selection.json', 'gazebo_waypoint_mission.py', 'adaptive_views.py', 'jk_pilot_ok'):
            self.assertIn(f, s)


if __name__ == '__main__':
    unittest.main()
