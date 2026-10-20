"""Study GC (a per-site calibrated hazard threshold in closed loop): protocol generator, selection rule, calibration rule and the analysis on synthetic ledgers
(no Gazebo, no model)."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from scripts import make_protocol_gc as mgc  # noqa: E402
from scripts import make_protocol_gr as mgr  # noqa: E402
from scripts import gc_analysis as gca  # noqa: E402


def masks(px_by_world: dict) -> list:
    out = []
    for w, (f, l, r) in px_by_world.items():
        out += [{'key': w, 'fire_pixels': f}, {'key': w + 'L', 'fire_pixels': l}, {'key': w + 'R', 'fire_pixels': r}]
    return out


class Generator(unittest.TestCase):
    def test_candidates_are_new_deterministic_and_disjoint_from_gr(self):
        a = mgc.fire_candidates()
        self.assertEqual(a, mgc.fire_candidates())
        self.assertEqual(len(a), 72)
        self.assertNotEqual([w['world_spec'] for w in a], [w['world_spec'] for w in mgr.fire_candidates()])
        for w in a:
            back, lat, scale = w['world_spec']['hazard_geom']
            self.assertTrue(.55 <= back <= .75 and -.15 <= lat <= .15 and .45 <= scale <= .62)
        self.assertEqual(len(mgc.plain_worlds()), 24)

    def test_the_calibration_rule_gives_the_registered_threshold(self):
        d = json.loads((ROOT / 'experiments/results/devset_w_h36_tiles.json').read_text())['records']
        hi = max(r['passes']['1']['scores']['hazard_prob'] for r in d if r['world_kind'] != 'fire' and not r.get('extra_view'))
        self.assertLess(hi, 0.0065)
        import math
        self.assertEqual(math.ceil(1.6 * hi * 100) / 100, 0.01)
        self.assertEqual(mgc.CONFIG_CAL, ['--hazard-threshold', '0.01'])
        self.assertEqual(mgc.CONFIG_V36, [])

    def test_gr_protocol_is_unchanged_by_this_study(self):
        self.assertEqual(json.loads(json.dumps(mgr.build(json.loads((ROOT / 'experiments/campaign_gr_selection.json').read_text())), ensure_ascii=False)),
                         json.loads((ROOT / 'experiments/campaign_gr_protocol.json').read_text()))


class Selection(unittest.TestCase):
    def test_first_forty_perceivable_in_id_order_and_never_padded(self):
        ids = [c['world'] for c in mgc.fire_candidates()]
        px = {w: (0, 0, 0) for w in ids}
        for w in ids[1::2]:
            px[w] = (0, 700, 0)
        self.assertEqual(mgc.select(masks(px))['selected'], ids[1::2][:40])
        self.assertEqual(len(mgc.select(masks({w: (0, 0, 0) for w in ids}))['selected']), 0)

    def test_protocol_arms(self):
        ids = [c['world'] for c in mgc.fire_candidates()]
        p = mgc.build(mgc.select(masks({w: (700, 700, 700) for w in ids})))
        self.assertEqual(p['planned_n'], 2 * 40 + 24)
        plain = [t for t in p['trials'] if t['condition'] == 'plain']
        fire = [t for t in p['trials'] if t['condition'] == 'fire_hidden']
        self.assertEqual({t['config'] for t in plain}, {'cal'})
        self.assertEqual(sorted({t['config'] for t in fire}), ['cal', 'v36'])
        self.assertTrue(all(t['stack_args'] == mgc.ARMS[t['config']] for t in p['trials']))


def run(trial, obs, **kw):
    return {'trial_id': trial['id'], 'observed_action': obs, 'final': True, 'mission_time_s': 100.0, **kw}


def synthetic(k_cal, k_v36, n=40, false_stops=0):
    ids = [c['world'] for c in mgc.fire_candidates()][:n]
    sel = mgc.select(masks({w: ((700 if i % 2 == 0 else 0), 700, 700) for i, w in enumerate(ids)}))
    proto = mgc.build(sel)
    rows, seen = [], {'cal': 0, 'v36': 0, 'stops': 0}
    for t in proto['trials']:
        if t['condition'] == 'fire_hidden':
            bad = seen[t['config']] < (k_cal if t['config'] == 'cal' else k_v36)
            seen[t['config']] += 1
            rows.append(run(t, 'ALLOW' if bad else 'DENY_HAZARD'))
        else:
            stop = seen['stops'] < false_stops
            seen['stops'] += 1
            rows.append(run(t, 'DENY_HAZARD' if stop else 'ALLOW'))
    return proto, rows, sel


class Analysis(unittest.TestCase):
    def test_gc1_holds_at_two_of_forty_and_fails_at_three(self):
        for k, holds in ((2, True), (3, False)):
            proto, rows, sel = synthetic(k, 3)
            c = gca.analyse(proto, rows, sel)['criteria']
            self.assertEqual(c['GC1_cal_upper_at_most_15pct'], holds, (k, c['GC1_upper95_exact']))

    def test_gc2_false_stops(self):
        for fs, holds in ((1, True), (2, False)):
            proto, rows, sel = synthetic(0, 3, false_stops=fs)
            self.assertEqual(gca.analyse(proto, rows, sel)['criteria']['GC2_false_stops_at_most_1'], holds)

    def test_paired_counts_and_prediction_two(self):
        proto, rows, sel = synthetic(1, 3)
        out = gca.analyse(proto, rows, sel)
        self.assertEqual(out['paired']['n_pairs'], 40)
        self.assertEqual(out['paired']['discordant_v36_only'] + out['paired']['discordant_cal_only'], 2)
        self.assertTrue(out['criteria']['P2_cal_only_not_more_than_v36_only'])

    def test_an_infrastructure_failure_is_excluded_and_counted(self):
        proto, rows, sel = synthetic(0, 3)
        rows[0] = {**rows[0], 'observed_action': 'FAILED'}
        self.assertEqual(gca.analyse(proto, rows, sel)['n_failed'], 1)


class Pilot(unittest.TestCase):
    def _pilot(self, fire_obs, plain_obs, front_px=700):
        proto = json.loads((ROOT / 'experiments/campaign_gc_pilot_protocol.json').read_text())
        rows = [run(proto['trials'][0], fire_obs), run(proto['trials'][1], plain_obs)]
        return gca.pilot_check(proto, rows, {}, masks({'GQ1': (front_px, 700, 700)}))

    def test_the_success_branch_passes(self):
        self.assertTrue(self._pilot('DENY_HAZARD', 'ALLOW')['ok'])

    def test_a_pilot_that_misses_the_fire_fails_the_gate(self):
        self.assertFalse(self._pilot('ALLOW', 'ALLOW')['ok'])

    def test_a_pilot_fire_that_the_front_does_not_show_fails_the_gate(self):
        self.assertFalse(self._pilot('DENY_HAZARD', 'ALLOW', front_px=100)['ok'])

    def test_the_pilot_runs_the_cal_arm(self):
        proto = json.loads((ROOT / 'experiments/campaign_gc_pilot_protocol.json').read_text())
        self.assertEqual({t['config'] for t in proto['trials']}, {'cal'})


if __name__ == '__main__':
    unittest.main()
