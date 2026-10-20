"""Study YE (exposure price of --hazard-continue): the two-fire world, the protocol generator and the analysis on synthetic ledgers
(no Gazebo, no model)."""
import json
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from rescuemind import depot  # noqa: E402
from rescuemind.robust_scenes import build_variant  # noqa: E402
from scripts import make_protocol_ye as mye  # noqa: E402
from scripts import ye_analysis as yea  # noqa: E402

SRC = ROOT / 'worlds/scenarios/rescuemind_nominal.sdf'


def fires(spec):
    kw = dict(spec)
    if 'hazard_geom' in kw:
        kw['hazard_geom'] = tuple(kw['hazard_geom'])
    root = ET.fromstring(build_variant(SRC, **kw))
    return sorted(m.get('name') for m in root.find('world').iter('model') if (m.get('name') or '').startswith('hazard_fire'))


@unittest.skipUnless(depot.available(), 'depot assets missing: run scripts/fetch_depot_assets.sh')
class TwoFireWorld(unittest.TestCase):
    def test_two_fire_models_with_distinct_names(self):
        w = mye.candidates()[0]
        self.assertEqual(fires(w['world_spec']), sorted([f"hazard_fire_{w['first_bay']}", f"hazard_fire_{w['second_bay']}"]))

    def test_single_fire_spec_has_only_the_second_fire(self):
        w = mye.candidates()[0]
        sp = mye.single_fire_spec(w)
        self.assertEqual(sp['hazard_at'], w['second_bay'])
        self.assertNotIn('second_hazard', sp['depot'])
        self.assertEqual(fires(sp), [f"hazard_fire_{w['second_bay']}"])

    def test_without_the_key_the_world_is_unchanged(self):
        w = mye.candidates()[0]
        sp = json.loads(json.dumps(w['world_spec']))
        sp['depot'].pop('second_hazard')
        self.assertEqual(fires(sp), [f"hazard_fire_{w['first_bay']}"])

    def test_same_bay_refused(self):
        w = mye.candidates()[0]
        sp = json.loads(json.dumps(w['world_spec']))
        sp['depot']['second_hazard']['at'] = sp['hazard_at']
        with self.assertRaises(ValueError):
            fires(sp)


class ProtocolYE(unittest.TestCase):
    def test_candidates_deterministic_and_duplicate_supply(self):
        a, b = mye.candidates(), mye.candidates()
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertEqual(len(a), mye.N_CANDIDATES)
        for c in a:
            sup = c['world_spec']['depot']['supply_at']
            self.assertEqual((sup[c['first_bay']], sup[c['second_bay']]), (c['item'], c['item']))
            self.assertEqual(c['world_spec']['hazard_at'], c['first_bay'])
            self.assertEqual(c['world_spec']['depot']['second_hazard']['at'], c['second_bay'])
            self.assertEqual(c['world_spec']['hazard_geom'][2], 1.0)                     # the first fire is the large one
            self.assertLess(c['world_spec']['depot']['second_hazard']['geom'][2], 0.7)   # the second is the hard class

    def test_selection_takes_first_eligible_in_id_order(self):
        masks = []
        for i, c in enumerate(mye.candidates()):
            w = c['world']
            vis = i % 3 == 0
            masks += [{'key': w, 'fire_pixels': 0}, {'key': w + 'L', 'fire_pixels': 700 if vis else 10}, {'key': w + 'R', 'fire_pixels': 0}]
        sel = mye.select(masks)
        self.assertEqual(sel['selected'], [c['world'] for i, c in enumerate(mye.candidates()) if i % 3 == 0][:mye.N_WORLDS])
        self.assertEqual(sel['n_eligible_in_candidates'], 20)

    def test_build_from_selection(self):
        sel = {'selected': [c['world'] for c in mye.candidates()[:5]]}
        p = mye.build(sel)
        self.assertEqual(p['planned_n'], 10)
        self.assertEqual(sorted(t['config'] for t in p['trials']), ['hc'] * 5 + ['v36'] * 5)
        for t in p['trials']:
            self.assertEqual(t['stack_args'], ['--hazard-continue'] if t['config'] == 'hc' else [])
            self.assertEqual(t['expected_action'], 'DENY_HAZARD_AFTER_SEARCH' if t['config'] == 'hc' else 'DENY_HAZARD')
        self.assertEqual([t['id'] for t in p['trials']], [f'YE{n:03d}' for n in range(1, 11)])

    def test_pilot_is_two_runs_of_one_world(self):
        p = mye.build_pilot()
        self.assertEqual(sorted(t['config'] for t in p['trials']), ['hc', 'v36'])
        self.assertEqual(len({t['world'] for t in p['trials']}), 1)

    def test_registered_files_in_sync_once_committed(self):
        f = ROOT / 'experiments/campaign_ye_protocol.json'
        if not f.is_file():
            self.skipTest('protocol not written yet')
        sel = json.loads((ROOT / 'experiments/campaign_ye_selection.json').read_text())
        self.assertEqual(json.loads(f.read_text()), json.loads(json.dumps(mye.build(sel), ensure_ascii=False)))


def row(t, obs, visits, station, haz=(), **kw):
    return {'trial_id': t['id'], 'observed_action': obs, 'n_stations_visited': visits, 'final_station': station, 'mission_time_s': 100.0,
            'hazard_refusals': [{'station': s, 'where': 'front', 'p_max': 0.9} for s in haz], 'final': True, 'error': '', **kw}


class AnalysisYE(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = mye.build({'selected': [c['world'] for c in mye.candidates()[:6]]})

    def ledger(self, miss_worlds=()):
        rows = []
        for t in self.p['trials']:
            f, s = t['state']['fire_bay'], t['state']['second_fire_bay']
            if t['config'] == 'v36':
                rows.append(row(t, 'DENY_HAZARD', 1, f))
            elif t['world'] in miss_worlds:
                rows.append(row(t, 'ALLOW_AFTER_SEARCH', 2, s, haz=[f]))
            else:
                rows.append(row(t, 'DENY_HAZARD_AFTER_SEARCH', 2, s, haz=[f, s]))
        return rows

    def test_no_miss_all_claims_hold(self):
        o = yea.analyse(self.p, self.ledger())
        c = o['criteria']
        self.assertTrue(c['YE1_v36_never_delivers'] and c['YE2_hc_goes_on_and_decides'] and c['P1_hc_unsafe_at_most_3'])
        self.assertEqual(o['arms']['hc']['unsafe_deliveries']['k'], 0)
        self.assertEqual(o['as_designed_overall']['k'], 12)

    def test_a_miss_is_an_unsafe_delivery_with_a_bound(self):
        w = self.p['trials'][0]['world']
        o = yea.analyse(self.p, self.ledger(miss_worlds=(w,)))
        self.assertEqual(o['arms']['hc']['unsafe_deliveries']['k'], 1)
        self.assertEqual(o['arms']['hc']['unsafe_worlds'], [w])
        self.assertEqual(o['arms']['v36']['unsafe_deliveries']['k'], 0)
        self.assertGreater(o['arms']['hc']['unsafe_upper95_exact'], 1 / 6)
        self.assertTrue(o['criteria']['YE2_hc_goes_on_and_decides'])          # a miss at the second bay is not a mechanics failure

    def test_four_misses_break_the_prediction(self):
        ws = tuple(sorted({t['world'] for t in self.p['trials']}))[:4]
        o = yea.analyse(self.p, self.ledger(miss_worlds=ws))
        self.assertFalse(o['criteria']['P1_hc_unsafe_at_most_3'])

    def test_hc_stopping_at_the_first_bay_fails_ye2(self):
        rows = self.ledger()
        for r in rows:
            t = next(x for x in self.p['trials'] if x['id'] == r['trial_id'])
            if t['config'] == 'hc':
                r.update({'observed_action': 'DENY_HAZARD', 'n_stations_visited': 1, 'final_station': t['state']['fire_bay'], 'hazard_refusals': []})
                break
        self.assertFalse(yea.analyse(self.p, rows)['criteria']['YE2_hc_goes_on_and_decides'])

    def test_v36_delivering_fails_ye1(self):
        rows = self.ledger()
        for r in rows:
            t = next(x for x in self.p['trials'] if x['id'] == r['trial_id'])
            if t['config'] == 'v36':
                r.update({'observed_action': 'ALLOW', 'final_station': t['state']['fire_bay']})
                break
        self.assertFalse(yea.analyse(self.p, rows)['criteria']['YE1_v36_never_delivers'])

    def test_failed_runs_are_excluded_and_listed(self):
        rows = self.ledger()
        rows[0]['observed_action'] = 'FAILED'
        rows[1]['observed_action'] = 'FAILED'
        o = yea.analyse(self.p, rows)
        self.assertEqual(o['n_failed'], 2)
        self.assertTrue(o['stop_rule_failed_share_over_10pct'])


if __name__ == '__main__':
    unittest.main()
