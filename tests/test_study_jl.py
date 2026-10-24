"""Study JL: protocol (fresh worlds, two interleaved arms), the registered claims on synthetic ledgers and the run script's guards."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import make_protocol_jl as mjl  # noqa: E402
from scripts import jl_analysis as jl  # noqa: E402


def fake_selection(n=100):
    return {'selected': [c['world'] for c in mjl.fire_candidates()[:n]], 'design_pixels': {}}


class Protocol(unittest.TestCase):
    def test_worlds_are_fresh_and_named(self):
        c = mjl.fire_candidates()
        self.assertEqual((len(c), c[0]['world'], c[-1]['world']), (132, 'JL001', 'JL132'))
        self.assertEqual(mjl.plain_worlds()[0]['world'], 'JLP01')
        from scripts import make_protocol_gm as gm
        old = {json.dumps(x['world_spec'], sort_keys=True) for x in gm.fire_candidates()}
        self.assertEqual(sum(json.dumps(x['world_spec'], sort_keys=True) in old for x in c), 0)       # no GM world is reused
        self.assertEqual(gm.SEED, 'GM-2026')                                                          # the seed swap is restored

    def test_two_interleaved_arms(self):
        p = mjl.build(fake_selection())
        self.assertEqual(p['planned_n'], 264)
        self.assertEqual({t['config'] for t in p['trials']}, {'v36', 'adapt'})
        self.assertEqual([t['stack_args'] for t in p['trials'] if t['config'] == 'adapt'][0], ['--adaptive-views', '0.8', '--adaptive-near', '0'])
        self.assertEqual([t['stack_args'] for t in p['trials'] if t['config'] == 'v36'][0], [])
        worlds = {}
        for t in p['trials']:
            worlds.setdefault(t['world'], set()).add(t['config'])
        self.assertTrue(all(v == {'v36', 'adapt'} for v in worlds.values()))

    def test_committed_candidates_match_the_generator(self):
        self.assertEqual(json.loads(mjl.CANDIDATES.read_text()), json.loads(json.dumps(mjl.candidates_protocol())))


class Claims(unittest.TestCase):
    def synthetic(self, v36_unsafe, adapt_unsafe, adapt_false_stops):
        sel = fake_selection()
        p = mjl.build(sel)
        fire = sel['selected']
        plain = [w['world'] for w in mjl.plain_worlds()]
        bad = {'v36': set(fire[:v36_unsafe]), 'adapt': set(fire[:adapt_unsafe])}
        fs = set(plain[:adapt_false_stops])
        rows = {}
        for t in p['trials']:
            if t['condition'] == 'fire_hidden':
                obs = 'ALLOW' if t['world'] in bad[t['config']] else 'DENY_HAZARD'
            else:
                obs = 'DENY_HAZARD' if (t['config'] == 'adapt' and t['world'] in fs) else 'ALLOW'
            rows[t['id']] = {'trial_id': t['id'], 'observed_action': obs, 'mission_time_s': 40.0, 'run_id': None, 'final': True}
        return jl.analyse(p, rows, sel)

    def test_holding_case(self):
        c = self.synthetic(14, 3, 1)['criteria']
        self.assertTrue(c['JL1_paired_one_sided_p_below_005_and_fewer'] and c['JL2_adapt_upper_at_most_10pct'] and c['JL3_false_stops_at_most_3'])

    def test_lines(self):
        self.assertTrue(self.synthetic(14, 4, 0)['criteria']['JL2_adapt_upper_at_most_10pct'])
        self.assertFalse(self.synthetic(14, 5, 0)['criteria']['JL2_adapt_upper_at_most_10pct'])
        self.assertFalse(self.synthetic(14, 3, 4)['criteria']['JL3_false_stops_at_most_3'])
        self.assertFalse(self.synthetic(10, 10, 0)['criteria']['JL1_paired_one_sided_p_below_005_and_fewer'])


class Guards(unittest.TestCase):
    def test_run_script(self):
        s = (ROOT / 'scripts/jl_run.sh').read_text()
        self.assertIn('flock 9', s)
        for f in ('PREREGISTRATION_JL.md', 'gazebo_waypoint_mission.py', 'local_run_audit.py', 'v32_orchestrate.py', 'jk_summary.json', 'selection and protocol'):
            self.assertIn(f, s)


if __name__ == '__main__':
    unittest.main()
