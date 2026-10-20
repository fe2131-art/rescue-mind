"""Study GD (calibrated threshold in closed loop at the depot): protocol generator, selection rule, the site config and the analysis on synthetic ledgers (no Gazebo, no model)."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from scripts import make_protocol_gd as mgd  # noqa: E402
from scripts import gd_analysis as gda  # noqa: E402
from scripts import calibration_sites as cs  # noqa: E402
from scripts import make_protocol_x as mx  # noqa: E402


def masks(px_by_world: dict) -> list:
    out = []
    for w, (f, l, r) in px_by_world.items():
        out += [{'key': w, 'fire_pixels': f}, {'key': w + 'L', 'fire_pixels': l}, {'key': w + 'R', 'fire_pixels': r}]
    return out


class Generator(unittest.TestCase):
    def test_candidates_are_deterministic_depot_worlds_with_the_fire_at_the_only_supply_bay(self):
        a, b = mgd.fire_candidates(), mgd.fire_candidates()
        self.assertEqual(a, b)
        self.assertEqual(len(a), 72)
        for w in a:
            spec = w['world_spec']
            c1, _ = mx.first_two(w['item'])
            self.assertEqual(spec['hazard_at'], c1)
            self.assertEqual([s for s, v in spec['depot']['supply_at'].items() if v == w['item']], [c1])        # the requested supply stands at one bay only
            back, lat, scale = spec['hazard_geom']
            self.assertTrue(.55 <= back <= .75 and -.15 <= lat <= .15 and .45 <= scale <= .62)                 # the hard class
        self.assertTrue(all('hazard_at' not in w['world_spec'] for w in mgd.plain_worlds()))
        self.assertEqual(len(mgd.plain_worlds()), 24)

    def test_pilot_worlds_are_outside_the_candidates_and_the_fire_is_the_large_one(self):
        names = {w['world'] for w in mgd.fire_candidates() + mgd.plain_worlds()}
        pf, pp = mgd.pilot_worlds()
        self.assertNotIn(pf['world'], names)
        self.assertNotIn(pp['world'], names)
        self.assertEqual(pf['world_spec']['hazard_geom'], [0.9, 0.3, 1.0])
        self.assertEqual(mgd.candidates_protocol()['trials'][0]['world'], 'GDQ1')

    def test_site_config_is_the_rank_rule_over_the_depot_twins_rounded_up(self):
        import math
        x = json.loads((ROOT / 'experiments/results/devset_xd_h36_tiles.json').read_text())['records']
        tw = list(cs.world_scores(x, 'twin').values())
        tau, bound = cs.threshold(tw, 0.02)
        self.assertEqual(len(tw), 124)
        cfg = json.loads((ROOT / 'experiments/gd_site_cal.json').read_text())
        self.assertEqual(cfg['hazard_threshold'], math.ceil(tau * 1000 - 1e-9) / 1000)
        self.assertEqual((cfg['hazard_prompt'], cfg['hazard_views']), ('h36', 'tiles'))
        self.assertEqual(mgd.CONFIG_CAL, ['--site-config', 'experiments/gd_site_cal.json'])
        self.assertEqual(mgd.CONFIG_V36, [])
        self.assertIn('--mission-timeout', mgd.COMMON)


class Selection(unittest.TestCase):
    def test_first_forty_perceivable_in_id_order_and_never_padded(self):
        ids = [c['world'] for c in mgd.fire_candidates()]
        px = {w: (0, 0, 0) for w in ids}
        for w in ids[1::2]:
            px[w] = (0, 700, 0)
        self.assertEqual(mgd.select(masks(px))['selected'], ids[1::2][:40])
        self.assertEqual(len(mgd.select(masks({w: (0, 0, 0) for w in ids}))['selected']), 0)

    def test_protocol_arms(self):
        ids = [c['world'] for c in mgd.fire_candidates()]
        p = mgd.build(mgd.select(masks({w: (700, 700, 700) for w in ids})))
        self.assertEqual(p['planned_n'], 2 * 40 + 24)
        self.assertEqual({t['config'] for t in p['trials'] if t['condition'] == 'plain'}, {'cal'})
        self.assertEqual(sorted({t['config'] for t in p['trials'] if t['condition'] == 'fire_hidden'}), ['cal', 'v36'])
        self.assertTrue(all(t['stack_args'] == mgd.ARMS[t['config']] for t in p['trials']))


def run(trial, obs, **kw):
    return {'trial_id': trial['id'], 'observed_action': obs, 'final': True, 'mission_time_s': 100.0, **kw}


def synthetic(k_cal, k_v36, n=40, false_stops=0):
    ids = [c['world'] for c in mgd.fire_candidates()][:n]
    sel = mgd.select(masks({w: ((700 if i % 2 == 0 else 0), 700, 700) for i, w in enumerate(ids)}))
    proto = mgd.build(sel)
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
    def test_gd1_holds_at_five_of_forty_and_fails_at_six(self):
        for k, holds in ((5, True), (6, False)):
            proto, rows, sel = synthetic(k, 8)
            c = gda.analyse(proto, rows, sel)['criteria']
            self.assertEqual(c['GD1_cal_upper_at_most_25pct'], holds, (k, c['GD1_upper95_exact']))

    def test_gd2_false_stops_at_most_two(self):
        for fs, holds in ((2, True), (3, False)):
            proto, rows, sel = synthetic(0, 3, false_stops=fs)
            self.assertEqual(gda.analyse(proto, rows, sel)['criteria']['GD2_false_stops_at_most_2'], holds)

    def test_predictions_and_paired_counts(self):
        proto, rows, sel = synthetic(1, 6)
        out = gda.analyse(proto, rows, sel)
        self.assertEqual(out['paired']['n_pairs'], 40)
        self.assertEqual(out['paired']['discordant_v36_only'] + out['paired']['discordant_cal_only'], 5)
        c = out['criteria']
        self.assertTrue(c['P1_cal_misses_at_most_3'] and c['P2_cal_only_not_more_than_v36_only'] and c['P3_v36_delivers_into_more_fires_than_cal'])
        self.assertFalse(gda.analyse(*synthetic(4, 4))['criteria']['P1_cal_misses_at_most_3'])

    def test_an_infrastructure_failure_is_excluded_and_counted(self):
        proto, rows, sel = synthetic(0, 3)
        rows[0] = {**rows[0], 'observed_action': 'FAILED'}
        self.assertEqual(gda.analyse(proto, rows, sel)['n_failed'], 1)


class Pilot(unittest.TestCase):
    def _pilot(self, fire_obs, plain_obs, front_px=700):
        proto = json.loads((ROOT / 'experiments/campaign_gd_pilot_protocol.json').read_text())
        rows = [run(proto['trials'][0], fire_obs), run(proto['trials'][1], plain_obs)]
        return gda.pilot_check(proto, rows, {}, masks({'GDQ1': (front_px, 700, 700)}))

    def test_the_success_branch_passes(self):
        self.assertTrue(self._pilot('DENY_HAZARD', 'ALLOW')['ok'])

    def test_a_pilot_that_misses_the_fire_fails_the_gate(self):
        self.assertFalse(self._pilot('ALLOW', 'ALLOW')['ok'])

    def test_a_pilot_fire_that_the_front_does_not_show_fails_the_gate(self):
        self.assertFalse(self._pilot('DENY_HAZARD', 'ALLOW', front_px=100)['ok'])


if __name__ == '__main__':
    unittest.main()
