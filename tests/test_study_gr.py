"""Study GR (closed-loop miss rate of the look-around on fresh worlds): protocol generator, selection rule and the analysis on synthetic ledgers
(no Gazebo, no model)."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from scripts import make_protocol_gr as mgr  # noqa: E402
from scripts import gr_analysis as gra  # noqa: E402
from scripts import make_protocol_f, make_protocol_g, make_protocol_j  # noqa: E402


def masks(px_by_world: dict) -> list:
    out = []
    for w, (f, l, r) in px_by_world.items():
        out += [{'key': w, 'fire_pixels': f}, {'key': w + 'L', 'fire_pixels': l}, {'key': w + 'R', 'fire_pixels': r}]
    return out


class Generator(unittest.TestCase):
    def test_candidates_are_deterministic_and_fire_worlds_have_a_fire_behind_the_requested_station(self):
        a, b = mgr.fire_candidates(), mgr.fire_candidates()
        self.assertEqual(a, b)
        self.assertEqual(len(a), 72)
        for w in a:
            self.assertEqual(w['world_spec']['hazard_at'], w['item'])
            back, lat, scale = w['world_spec']['hazard_geom']
            self.assertTrue(.55 <= back <= .75 and -.15 <= lat <= .15 and .45 <= scale <= .62)
        self.assertTrue(all('hazard_at' not in w['world_spec'] for w in mgr.plain_worlds()))

    def test_pilot_worlds_are_outside_the_candidates_and_the_fire_is_the_large_one(self):
        names = {w['world'] for w in mgr.fire_candidates() + mgr.plain_worlds()}
        pf, pp = mgr.pilot_worlds()
        self.assertNotIn(pf['world'], names)
        self.assertNotIn(pp['world'], names)
        self.assertEqual(pf['world_spec']['hazard_geom'], [0.55, 0.0, 0.62])
        self.assertEqual(mgr.candidates_protocol()['trials'][0]['world'], 'GP1')

    def test_the_earlier_protocols_are_unchanged_by_this_study(self):
        for mod, name in ((make_protocol_g, 'campaign_g_protocol.json'), (make_protocol_j, 'campaign_j_protocol.json')):
            self.assertEqual(json.loads(json.dumps(mod.build(), ensure_ascii=False)), json.loads((ROOT / 'experiments' / name).read_text()), name)


class Selection(unittest.TestCase):
    def test_first_forty_perceivable_in_id_order_and_never_padded(self):
        ids = [c['world'] for c in mgr.fire_candidates()]
        px = {w: (0, 0, 0) for w in ids}
        for w in ids[1::2]:                       # every second candidate shows the fire from a side pose
            px[w] = (0, 700, 0)
        sel = mgr.select(masks(px))
        self.assertEqual(sel['selected'], ids[1::2][:40])
        self.assertEqual(sel['n_eligible_in_candidates'], 36)
        self.assertEqual(len(mgr.select(masks({w: (0, 0, 0) for w in ids}))['selected']), 0)

    def test_613_pixels_is_not_perceivable_and_614_is(self):
        ids = [c['world'] for c in mgr.fire_candidates()][:2]
        sel = mgr.select(masks({ids[0]: (613, 613, 613), ids[1]: (0, 0, 614)}))
        self.assertEqual(sel['selected'], [ids[1]])

    def test_protocol_has_both_arms_on_fire_worlds_and_one_run_on_each_fire_free_world(self):
        ids = [c['world'] for c in mgr.fire_candidates()]
        sel = mgr.select(masks({w: (700, 700, 700) for w in ids}))
        p = mgr.build(sel)
        self.assertEqual(p['planned_n'], 2 * 40 + 12)
        fire = [t for t in p['trials'] if t['condition'] == 'fire_hidden']
        plain = [t for t in p['trials'] if t['condition'] == 'plain']
        self.assertEqual({t['config'] for t in plain}, {'v36'})
        self.assertEqual(len(plain), 12)
        self.assertEqual(sorted({t['config'] for t in fire}), ['front', 'v36'])
        self.assertTrue(all(t['stack_args'] == mgr.ARMS[t['config']] for t in p['trials']))
        self.assertEqual(mgr.CONFIG_V36, make_protocol_j.CONFIG_A)               # v36 is the orchestrator defaults, as J's arm A
        self.assertEqual(mgr.CONFIG_FRONT, ['--look-around', '0'])


def run(trial, obs, **kw):
    return {'trial_id': trial['id'], 'observed_action': obs, 'final': True, 'mission_time_s': 100.0, **kw}


def synthetic(k_v36, k_front, n=40, false_stops=0):
    ids = [c['world'] for c in mgr.fire_candidates()][:n]
    sel = mgr.select(masks({w: ((700 if i % 2 == 0 else 0), 700, 700) for i, w in enumerate(ids)}))
    proto = mgr.build(sel)
    rows, seen = [], {'front': 0, 'v36': 0, 'plainstops': 0}
    for t in proto['trials']:
        if t['condition'] == 'fire_hidden':
            bad = seen[t['config']] < (k_front if t['config'] == 'front' else k_v36)
            seen[t['config']] += 1
            rows.append(run(t, 'ALLOW' if bad else 'DENY_HAZARD'))
        else:
            stop = seen['plainstops'] < false_stops
            seen['plainstops'] += 1
            rows.append(run(t, 'DENY_HAZARD' if stop else 'ALLOW'))
    return proto, rows, sel


class Analysis(unittest.TestCase):
    def test_gr1_holds_at_three_of_forty_and_fails_at_four(self):
        for k, holds in ((3, True), (4, False)):
            proto, rows, sel = synthetic(k, 20)
            c = gra.analyse(proto, rows, sel)['criteria']
            self.assertEqual(c['GR1_v36_upper_at_most_20pct'], holds, (k, c['GR1_upper95_exact']))

    def test_gr2_needs_a_paired_improvement_with_p_below_005(self):
        proto, rows, sel = synthetic(1, 20)
        self.assertTrue(gra.analyse(proto, rows, sel)['criteria']['GR2_front_worse_and_mcnemar_p_below_005'])
        proto, rows, sel = synthetic(1, 2)
        self.assertFalse(gra.analyse(proto, rows, sel)['criteria']['GR2_front_worse_and_mcnemar_p_below_005'])

    def test_gr3_false_stops(self):
        for fs, holds in ((1, True), (2, False)):
            proto, rows, sel = synthetic(0, 20, false_stops=fs)
            self.assertEqual(gra.analyse(proto, rows, sel)['criteria']['GR3_false_stops_at_most_1'], holds)

    def test_an_infrastructure_failure_is_excluded_from_the_claims_and_counted(self):
        proto, rows, sel = synthetic(0, 20)
        rows[0] = {**rows[0], 'observed_action': 'FAILED'}
        out = gra.analyse(proto, rows, sel)
        self.assertEqual(out['n_failed'], 1)

    def test_strata_follow_the_front_design_mask(self):
        proto, rows, sel = synthetic(0, 20)
        strata = gra.analyse(proto, rows, sel)['arms']['v36']['fire']['strata']
        self.assertEqual(strata['front_visible']['n'] + strata['side_only']['n'], 40)
        self.assertEqual(strata['front_visible']['n'], 20)


class Pilot(unittest.TestCase):
    def _pilot(self, fire_obs, plain_obs, front_px=700):
        proto = json.loads((ROOT / 'experiments/campaign_gr_pilot_protocol.json').read_text())
        rows = [run(proto['trials'][0], fire_obs), run(proto['trials'][1], plain_obs)]
        return gra.pilot_check(proto, rows, {}, masks({'GP1': (front_px, 700, 700)}))

    def test_the_success_branch_passes(self):
        self.assertTrue(self._pilot('DENY_HAZARD', 'ALLOW')['ok'])

    def test_a_pilot_that_misses_the_fire_fails_the_gate(self):
        r = self._pilot('ALLOW', 'ALLOW')
        self.assertFalse(r['ok'])
        self.assertFalse(r['checks']['fire_world_refused_for_hazard'])

    def test_a_pilot_fire_that_the_front_does_not_show_fails_the_gate(self):
        self.assertFalse(self._pilot('DENY_HAZARD', 'ALLOW', front_px=100)['ok'])


if __name__ == '__main__':
    unittest.main()
