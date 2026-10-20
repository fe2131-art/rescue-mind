"""Study GV (wider look-around views with a calibrated threshold, closed loop at the depot): generator, selection, arms and the analysis on synthetic ledgers (no Gazebo, no model)."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from scripts import make_protocol_gv as mgv  # noqa: E402
from scripts import make_protocol_gd as mgd  # noqa: E402
from scripts import gv_analysis as gva  # noqa: E402
from scripts import make_protocol_x as mx  # noqa: E402


def masks(px_by_world: dict) -> list:
    out = []
    for w, (f, l, r) in px_by_world.items():
        out += [{'key': w, 'fire_pixels': f}, {'key': w + 'L', 'fire_pixels': l}, {'key': w + 'R', 'fire_pixels': r}]
    return out


class Generator(unittest.TestCase):
    def test_candidates_are_fresh_depot_worlds_with_the_hard_class_fire(self):
        a = mgv.fire_candidates()
        self.assertEqual(a, mgv.fire_candidates())
        self.assertEqual(len(a), 72)
        self.assertEqual({w['world'] for w in a} & {w['world'] for w in mgd.fire_candidates()}, set())       # other ids ...
        self.assertNotEqual([w['world_spec'] for w in a], [w['world_spec'] for w in mgd.fire_candidates()])  # ... and other worlds
        for w in a:
            spec = w['world_spec']
            c1, _ = mx.first_two(w['item'])
            self.assertEqual(spec['hazard_at'], c1)
            back, lat, scale = spec['hazard_geom']
            self.assertTrue(.55 <= back <= .75 and -.15 <= lat <= .15 and .45 <= scale <= .62)
        self.assertEqual(len(mgv.plain_worlds()), 24)
        self.assertEqual(len(mgv.calibration_worlds()), 100)

    def test_arms_and_the_wide_views(self):
        self.assertEqual(mgv.CONFIG_V36, [])
        self.assertEqual(mgv.CONFIG_WIDE, ['--look-around', '0.8'])
        self.assertEqual(mgv.CONFIG_WCAL, ['--look-around', '0.8', '--site-config', 'experiments/gv_site_cal.json'])
        self.assertEqual(mgv.CONFIG_OPEN[:2], ['--look-around', '0.8'])                                      # the calibration runs use the same views as the wcal arm
        self.assertEqual(json.loads((ROOT / 'experiments/gv_site_open.json').read_text())['hazard_threshold'], 1.0)
        cal = mgv.calibration_protocol()
        self.assertEqual(cal['planned_n'], 100)
        self.assertTrue(all(t['stack_args'] == mgv.CONFIG_OPEN and t['condition'] == 'plain' for t in cal['trials']))

    def test_protocol_has_three_arms_on_fire_worlds_and_two_on_fire_free_worlds(self):
        ids = [c['world'] for c in mgv.fire_candidates()]
        p = mgv.build(mgv.select(masks({w: (700, 700, 700) for w in ids})))
        self.assertEqual(p['planned_n'], 3 * 40 + 2 * 24)
        self.assertEqual(sorted({t['config'] for t in p['trials'] if t['condition'] == 'fire_hidden'}), ['v36', 'wcal', 'wide'])
        self.assertEqual(sorted({t['config'] for t in p['trials'] if t['condition'] == 'plain'}), ['wcal', 'wide'])
        self.assertTrue(all(t['stack_args'] == mgv.ARMS[t['config']] for t in p['trials']))


def run(trial, obs, **kw):
    return {'trial_id': trial['id'], 'observed_action': obs, 'final': True, 'mission_time_s': 100.0, **kw}


def synthetic(k, n=40, false_stops=0, time_wcal=100.0):
    """k = {'v36': .., 'wide': .., 'wcal': ..} unsafe deliveries; the first k worlds of each arm are unsafe."""
    ids = [c['world'] for c in mgv.fire_candidates()][:n]
    sel = mgv.select(masks({w: ((700 if i % 2 == 0 else 0), 700, 700) for i, w in enumerate(ids)}))
    proto = mgv.build(sel)
    rows, seen = [], {'v36': 0, 'wide': 0, 'wcal': 0, 'stops': 0}
    for t in proto['trials']:
        a = t['config']
        if t['condition'] == 'fire_hidden':
            bad = seen[a] < k[a]
            seen[a] += 1
            rows.append(run(t, 'ALLOW' if bad else 'DENY_HAZARD', mission_time_s=time_wcal if a == 'wcal' else 100.0))
        else:
            stop = a == 'wcal' and seen['stops'] < false_stops
            seen['stops'] += a == 'wcal'
            rows.append(run(t, 'DENY_HAZARD' if stop else 'ALLOW'))
    return proto, rows, sel


class Analysis(unittest.TestCase):
    def test_gv1_holds_at_two_of_forty_and_fails_at_three(self):
        for kc, holds in ((2, True), (3, False)):
            proto, rows, sel = synthetic({'v36': 8, 'wide': 4, 'wcal': kc})
            c = gva.analyse(proto, rows, sel)['criteria']
            self.assertEqual(c['GV1_wcal_upper_at_most_15pct'], holds, (kc, c['GV1_upper95_exact']))

    def test_gv2_false_stops_at_most_two(self):
        for fs, holds in ((2, True), (3, False)):
            proto, rows, sel = synthetic({'v36': 3, 'wide': 3, 'wcal': 0}, false_stops=fs)
            self.assertEqual(gva.analyse(proto, rows, sel)['criteria']['GV2_false_stops_at_most_2'], holds)

    def test_predictions_and_the_three_paired_comparisons(self):
        proto, rows, sel = synthetic({'v36': 8, 'wide': 4, 'wcal': 1})
        out = gva.analyse(proto, rows, sel)
        self.assertEqual(out['paired']['v36_vs_wcal']['n_pairs'], 40)
        self.assertEqual(out['paired']['v36_vs_wcal']['discordant_v36_only'], 7)                 # nested sets: 8 unsafe against 1
        self.assertLess(out['paired']['v36_vs_wcal']['mcnemar_p'], 0.05)
        c = out['criteria']
        self.assertTrue(c['P1_wcal_fewer_than_v36'] and c['P2_mcnemar_v36_vs_wcal_below_005'] and c['P3_wide_not_more_than_v36'] and c['P4_time_cost_at_most_20s'])
        c2 = gva.analyse(*synthetic({'v36': 3, 'wide': 5, 'wcal': 3}, time_wcal=130.0))['criteria']
        self.assertFalse(c2['P1_wcal_fewer_than_v36'] or c2['P3_wide_not_more_than_v36'] or c2['P4_time_cost_at_most_20s'])
        self.assertEqual(c2['time_cost_s'], 30.0)

    def test_an_infrastructure_failure_is_excluded_and_counted(self):
        proto, rows, sel = synthetic({'v36': 3, 'wide': 3, 'wcal': 0})
        rows[0] = {**rows[0], 'observed_action': 'FAILED'}
        self.assertEqual(gva.analyse(proto, rows, sel)['n_failed'], 1)


class Pilot(unittest.TestCase):
    def _pilot(self, fire_obs, plain_obs, front_px=700):
        proto = json.loads((ROOT / 'experiments/campaign_gv_pilot_protocol.json').read_text())
        rows = [run(proto['trials'][0], fire_obs), run(proto['trials'][1], plain_obs)]
        return gva.pilot_check(proto, rows, {}, masks({'GVQ1': (front_px, 700, 700)}))

    def test_the_success_branch_passes_and_a_missed_fire_fails_the_gate(self):
        self.assertTrue(self._pilot('DENY_HAZARD', 'ALLOW')['ok'])
        self.assertFalse(self._pilot('ALLOW', 'ALLOW')['ok'])
        self.assertTrue(self._pilot('DENY_HAZARD', 'DENY_HAZARD')['ok'])                      # a false alarm in the clean pilot world is recorded, not gated
        self.assertFalse(self._pilot('DENY_HAZARD', 'ALLOW', front_px=100)['ok'])
        self.assertEqual(json.loads((ROOT / 'experiments/campaign_gv_pilot_protocol.json').read_text())['trials'][0]['config'], 'wcal')


if __name__ == '__main__':
    unittest.main()
