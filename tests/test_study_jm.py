"""Study JM: twin worlds that differ only in the smoke plume, two interleaved arms, the registered claims on synthetic ledgers, the run script's guards."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import make_protocol_jm as mjm  # noqa: E402
from scripts import jm_analysis as jm  # noqa: E402


def fake_selection(n=60):
    return {'selected': [c['world'] for c in mjm.fire_candidates()[:n]], 'design_pixels': {}}


class Protocol(unittest.TestCase):
    def test_twins_differ_only_in_smoke(self):
        w = mjm.fire_candidates()[0]
        s, n = mjm.twin(w, True), mjm.twin(w, False)
        self.assertEqual((s['world'], n['world']), (w['world'] + 'S', w['world'] + 'N'))
        strip = lambda x: json.dumps({k: v for k, v in x['world_spec']['depot'].items() if k != 'particle_smoke'}, sort_keys=True)
        self.assertEqual(strip(s), strip(n))
        self.assertEqual({s['world_spec']['depot']['particle_smoke'], n['world_spec']['depot']['particle_smoke']}, {True, False})
        self.assertEqual({k: v for k, v in s['world_spec'].items() if k != 'depot'}, {k: v for k, v in n['world_spec'].items() if k != 'depot'})

    def test_runs_and_arms(self):
        p = mjm.build(fake_selection())
        self.assertEqual(p['planned_n'], 240)
        self.assertEqual({t['config'] for t in p['trials']}, {'v36', 'adapt'})
        self.assertEqual([t['stack_args'] for t in p['trials'] if t['config'] == 'adapt'][0], ['--adaptive-views', '0.8', '--adaptive-near', '0'])
        cells = {}
        for t in p['trials']:
            cells.setdefault(t['world'], set()).add(t['config'])
        self.assertEqual(len(cells), 120)
        self.assertTrue(all(v == {'v36', 'adapt'} for v in cells.values()))

    def test_fresh_worlds(self):
        from scripts import make_protocol_gm as gm
        old = {json.dumps(x['world_spec']['depot'], sort_keys=True) for x in gm.fire_candidates()}
        new = [json.dumps(x['world_spec']['depot'], sort_keys=True) for x in mjm.fire_candidates()]
        self.assertEqual(sum(d in old for d in new), 0)
        self.assertEqual(gm.SEED, 'GM-2026')
        self.assertEqual(gm.N_CANDIDATES, 132)

    def test_committed_candidates_match_the_generator(self):
        self.assertEqual(json.loads(mjm.CANDIDATES.read_text()), json.loads(json.dumps(mjm.candidates_protocol())))


class Claims(unittest.TestCase):
    def synthetic(self, v36_s, v36_n, adapt_s, adapt_n):
        sel = fake_selection()
        p = mjm.build(sel)
        bases = sel['selected']
        bad = {('v36', 'S'): set(bases[:v36_s]), ('v36', 'N'): set(bases[:v36_n]), ('adapt', 'S'): set(bases[:adapt_s]), ('adapt', 'N'): set(bases[:adapt_n])}
        rows = {}
        for t in p['trials']:
            base, tw = t['world'][:-1], t['world'][-1]
            obs = 'ALLOW' if base in bad[(t['config'], tw)] else 'DENY_HAZARD'
            rows[t['id']] = {'trial_id': t['id'], 'observed_action': obs, 'mission_time_s': 40.0, 'run_id': None, 'final': True}
        return jm.analyse(p, rows, sel)

    def test_holding_case(self):
        c = self.synthetic(10, 2, 3, 0)['criteria']
        self.assertTrue(c['JM1_smoke_increases_v36_misses'] and c['JM2_extra_views_reduce_misses_in_smoke'] and c['JM3_adapt_smoke_at_most_4_of_60'] and c['P1_adapt_no_smoke_at_most_1'])

    def test_no_smoke_effect_and_budget_line(self):
        self.assertFalse(self.synthetic(5, 5, 3, 0)['criteria']['JM1_smoke_increases_v36_misses'])
        self.assertTrue(self.synthetic(10, 2, 4, 0)['criteria']['JM3_adapt_smoke_at_most_4_of_60'])
        self.assertFalse(self.synthetic(10, 2, 5, 0)['criteria']['JM3_adapt_smoke_at_most_4_of_60'])


class Guards(unittest.TestCase):
    def test_run_script(self):
        s = (ROOT / 'scripts/jm_run.sh').read_text()
        self.assertIn('flock 9', s)
        for f in ('PREREGISTRATION_JM.md', 'gazebo_waypoint_mission.py', 'local_run_audit.py', 'v32_orchestrate.py', 'selection and protocol'):
            self.assertIn(f, s)


if __name__ == '__main__':
    unittest.main()
