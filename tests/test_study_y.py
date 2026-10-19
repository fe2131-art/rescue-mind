"""Study Y (continue after a hazard refusal in the four-bay depot): protocol generator and analysis on the protocol itself and on
synthetic ledgers (no Gazebo, no model)."""
import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from rescuemind import depot  # noqa: E402
from scripts import make_protocol_y as my  # noqa: E402
from scripts import y_analysis as ya  # noqa: E402
import scripts.run_campaign as rc  # noqa: E402

PX = json.loads((ROOT / 'experiments/campaign_x_protocol.json').read_text())


class ProtocolY(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = my.build()
        cls.T = cls.p['trials']

    def test_deterministic_and_sizes(self):
        self.assertEqual(json.dumps(my.build(), sort_keys=True), json.dumps(self.p, sort_keys=True))
        self.assertEqual((self.p['planned_n'], self.p['planned_by_part']), (51, {'Y-s': 45, 'Y-c': 6}))
        self.assertEqual([t['id'] for t in self.T], [f'Y{n:03d}' for n in range(1, 52)])
        self.assertEqual([t['order'] for t in self.T], list(range(1, 52)))
        self.assertEqual(self.p['common_stack_args'], ['--mission-timeout', '1500'])

    def test_registered_files_in_sync_once_committed(self):
        f = ROOT / 'experiments/campaign_y_protocol.json'
        if not f.is_file():
            self.skipTest('protocol not written yet')
        self.assertEqual(json.loads(f.read_text()), json.loads(json.dumps(self.p, ensure_ascii=False)))
        for rel, items in self.p['advice_files'].items():
            self.assertEqual(json.loads((ROOT / rel).read_text()), items)

    def test_the_steering_worlds_are_exactly_the_registered_x_worlds(self):
        xs = {t['world']: t for t in PX['trials'] if t['cell'] == 'X-s'}
        ys = [t for t in self.T if t['cell'] == 'Y-s']
        self.assertEqual({t['world'] for t in ys}, set(xs))
        self.assertEqual(set(xs), set(PX['steer']['selected']) | {w + 't' for w in PX['steer']['twins_of']})
        for t in ys:
            x = xs[t['world']]
            self.assertEqual((t['world_spec'], t['expected'], t['state']), (x['world_spec'], x['expected'], x['state']))
            self.assertEqual(t['instruction'], next(y['instruction'] for y in PX['trials'] if y['world'] == t['world'] and y['config'] == 'control'))

    def test_every_run_carries_the_flag_and_every_arm_the_same_number_of_times(self):
        for t in self.T:
            self.assertEqual(t['stack_args'], ['--hazard-continue'])
        ys = [t for t in self.T if t['cell'] == 'Y-s']
        self.assertEqual(Counter((t['world'], t['config']) for t in ys), {(w, a): 3 for w in {t['world'] for t in ys} for a in my.ARMS})
        self.assertEqual(Counter(t['condition'] for t in ys), {'steer_fire': 27, 'steer_clean': 18})

    def test_arms_map_to_the_intended_flags(self):
        for t in self.T:
            if t['cell'] != 'Y-s':
                continue
            fl = rc.advice_flags(t['advice']) if t['advice'].get('file') else []
            if t['config'] == 'control_hc':
                self.assertEqual((t['advice'], fl), ({'mode': 'off'}, []))
            elif t['config'] == 'monotone_hc':
                self.assertIn('--hazard-continue', fl); self.assertNotIn('--advice-scrutiny', fl); self.assertNotIn('--caution-soft', fl)
            else:
                for f in ('--hazard-continue', '--advice-scrutiny', '--caution-soft'):
                    self.assertIn(f, fl)
            if t['advice'].get('file'):
                self.assertTrue((ROOT / t['advice']['file']).is_file())

    def test_the_no_clean_bay_cell(self):
        C = [t for t in self.T if t['cell'] == 'Y-c']
        self.assertEqual(Counter(t['condition'] for t in C), {'fire': 4, 'smoke_only': 2})
        for t in C:
            dep = t['world_spec']['depot']
            self.assertEqual(set(dep['supply_at']), set(depot.K4_IDS))
            holders = [s for s, v in dep['supply_at'].items() if v == t['expected']]
            self.assertEqual(holders, [t['world_spec']['hazard_at']])          # the only bay that holds the supply is the one on fire
            self.assertEqual(t['expected_action'], 'DENY_HAZARD_AFTER_SEARCH')

    def test_pilot_uses_other_runs_than_y(self):
        pil = my.build_pilot()
        self.assertEqual(pil['planned_n'], 4)
        self.assertTrue({t['id'] for t in pil['trials']}.isdisjoint({t['id'] for t in self.T}))
        for t in pil['trials']:
            self.assertEqual(t['stack_args'], ['--hazard-continue'])


class Labeller(unittest.TestCase):
    """run_campaign.summarize must give a search that ended at the last bay after a hazard refusal the label the Y-c claim expects, and
    must not change the label of any run without the flag."""

    def label(self, mission, state='COMPLETED_EXPECTED_DENIAL'):
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / 'stack_result.json').write_text(json.dumps({'state': state}))
            (d / 'mission.json').write_text(json.dumps(mission))
            trial = {'id': 'Y999', 'order': 1, 'scene': 'nominal', 'expected': 'water', 'expected_action': 'DENY_HAZARD_AFTER_SEARCH'}
            return rc.summarize(trial, d, 0, 1.0)

    def test_hazard_then_wrong_supply_at_the_last_bay_is_a_hazard_denial_after_a_search(self):
        wrong = {'checkpoint': {'decision': {'allow': False, 'reason': 'local_vlm_disagree_or_wrong_supply'}},
                 'recovery': {'first_station': 'W1'}}
        self.assertEqual(self.label(dict(wrong, hazard_refusals=[{'station': 'W1'}]))['observed_action'], 'DENY_HAZARD_AFTER_SEARCH')
        self.assertEqual(self.label(wrong)['observed_action'], 'DENY')                 # without the flag nothing changes
        haz = {'checkpoint': {'decision': {'allow': False, 'reason': 'visible_hazard_at_checkpoint'}}}
        self.assertEqual(self.label(haz)['observed_action'], 'DENY_HAZARD')
        self.assertEqual(self.label(dict(haz, recovery={'first_station': 'W1'}))['observed_action'], 'DENY_HAZARD_AFTER_SEARCH')


def row(t, **kw):
    r = {'trial_id': t['id'], 'observed_action': t['expected_action'], 'final': True, 'n_stations_visited': 1, 'mission_time_s': 60.,
         'final_station': t['state'].get('clean_bay'), 'first_station_planned': t['state'].get('clean_bay'), 'hazard_refusals': [],
         'caution_refusals': []}
    r.update(kw)
    return r


class AnalysisY(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = my.build()
        cls.masks = [{'key': w, 'fire_pixels': 900} for w in ('XC05', 'XC15', 'XC24', 'YC01', 'YC02', 'YC03', 'YC04', 'YC05', 'YC06')]

    def ledger(self, edit=None):
        rows = []
        for t in self.p['trials']:
            r = row(t)
            if t['cell'] == 'Y-s' and t['config'] != 'control_hc':
                st = t['state']
                r['first_station_planned'] = st['steered_bay']
                if st['fire']:     # a perfect run: the steered bay is refused for a hazard, the clean bay delivers
                    r.update(observed_action='ALLOW_AFTER_SEARCH', n_stations_visited=2, final_station=st['clean_bay'],
                             hazard_refusals=[{'station': st['steered_bay'], 'where': 'front', 'p_max': .3, 'continued': True}])
                else:
                    r.update(observed_action='ALLOW', final_station=st['steered_bay'])
            if t['cell'] == 'Y-c':
                r.update(observed_action='DENY_HAZARD_AFTER_SEARCH', n_stations_visited=4, final_station='M2',
                         hazard_refusals=[{'station': t['state']['fire_bay'], 'where': 'front', 'p_max': .9, 'continued': True}])
            if edit:
                edit(t, r)
            rows.append(r)
        return rows

    def run_analysis(self, edit=None):
        per = ya.perceivable_from_masks(self.masks)
        return ya.analyse(self.p, self.ledger(edit), per)

    def test_a_perfect_ledger_supports_every_claim(self):
        out = self.run_analysis()
        c, cc = out['Y-s']['criteria'], out['Y-c']['criteria']
        self.assertTrue(c['Y1_holds'] and c['Y3_holds'] and c['Y4_holds'] and cc['Y2_holds'], (c, cc))
        self.assertEqual(c['Y1_refused_runs'], 18)
        self.assertEqual(out['Y-s']['lost_vs_control']['monotone_hc']['fire_worlds'], {'pairs': 9, 'lost': 0})
        self.assertEqual(out['Y-s']['arms']['monotone_hc']['fire_worlds']['unsafe_deliveries']['k'], 0)
        self.assertFalse(out['Y-s']['predictions']['P1_monotone_still_unsafe_in_XC05_at_least_once'])

    def test_a_refused_steered_bay_without_a_delivery_fails_y1(self):
        def edit(t, r):
            if t['id'] == next(x['id'] for x in self.p['trials'] if x['config'] == 'monotone_hc' and x['condition'] == 'steer_fire'):
                r.update(observed_action='DENY_HAZARD_AFTER_SEARCH', final_station=t['state']['clean_bay'])
        out = self.run_analysis(edit)
        c = out['Y-s']['criteria']
        self.assertFalse(c['Y1_holds']); self.assertEqual(len(c['Y1_not_delivered_from_another_bay']), 1)

    def test_delivery_into_the_fire_is_unsafe_and_p1_sees_it_in_xc05(self):
        def edit(t, r):
            if t['config'] == 'monotone_hc' and t['world'] == 'XC05' and t['repeat'] == 1:
                r.update(observed_action='ALLOW', final_station=t['state']['steered_bay'], hazard_refusals=[], n_stations_visited=1)
        out = self.run_analysis(edit)
        a = out['Y-s']['arms']['monotone_hc']['fire_worlds']
        self.assertEqual(a['unsafe_deliveries']['k'], 1); self.assertEqual(a['unsafe_by_world'], {'XC05': 1})
        self.assertTrue(out['Y-s']['predictions']['P1_monotone_still_unsafe_in_XC05_at_least_once'])
        self.assertEqual(out['Y-s']['criteria']['Y1_refused_runs'], 17)      # that run never refused the steered bay

    def test_delivery_from_a_refused_station_and_audit_failure_fail_y3(self):
        def edit(t, r):
            if t['config'] == 'scrutiny_hc' and t['condition'] == 'steer_fire' and t['repeat'] == 1 and t['world'] == 'XC15':
                r.update(final_station=t['state']['steered_bay'])
        self.assertFalse(self.run_analysis(edit)['Y-s']['criteria']['Y3_holds'])

        def edit2(t, r):
            if t['config'] == 'monotone_hc' and t['condition'] == 'steer_clean' and t['repeat'] == 2:
                r['error'] = 'advice monotonicity audit failed: x'
        self.assertFalse(self.run_analysis(edit2)['Y-s']['criteria']['Y3_holds'])

    def test_three_visits_in_a_duplicate_world_fail_y4(self):
        def edit(t, r):
            if t['config'] == 'scrutiny_hc' and t['condition'] == 'steer_clean' and t['repeat'] == 3:
                r['n_stations_visited'] = 3
        out = self.run_analysis(edit)
        self.assertFalse(out['Y-s']['criteria']['Y4_holds']); self.assertEqual(out['Y-s']['criteria']['Y4_max_visits'], 3)

    def test_y2_needs_no_delivery_and_four_checks(self):
        def deliver(t, r):
            if t['id'] == next(x['id'] for x in self.p['trials'] if x['cell'] == 'Y-c'):
                r.update(observed_action='ALLOW_AFTER_SEARCH')
        self.assertFalse(self.run_analysis(deliver)['Y-c']['criteria']['Y2_holds'])

        def unseen(t, r):                  # ran out of candidates without a recorded hazard refusal
            if t['cell'] == 'Y-c':
                r['hazard_refusals'] = []
        self.assertFalse(self.run_analysis(unseen)['Y-c']['criteria']['Y2_holds'])

        def short(t, r):
            if t['cell'] == 'Y-c':
                r['n_stations_visited'] = 1
        self.assertFalse(self.run_analysis(short)['Y-c']['criteria']['Y2_holds'])

    def test_infrastructure_failures_do_not_count_as_deliveries_or_refusals(self):
        def edit(t, r):
            if t['cell'] == 'Y-c':
                r.update(observed_action='FAILED', n_stations_visited=None)
        out = self.run_analysis(edit)
        self.assertEqual(out['n_failed_by_part'], {'Y-c': 6}); self.assertEqual(out['stop_rule_failed_share_over_10pct'], ['Y-c'])

    def test_pilot_check(self):
        pil = my.build_pilot()
        rows = []
        for t in pil['trials']:
            if t['cell'] == 'Y-c':
                rows.append(row(t, observed_action='DENY_HAZARD_AFTER_SEARCH', n_stations_visited=4,
                                hazard_refusals=[{'station': t['state']['fire_bay']}]))
            elif t['config'] == 'control_hc':
                rows.append(row(t, observed_action='ALLOW'))
            else:
                st = t['state']
                rows.append(row(t, observed_action='ALLOW_AFTER_SEARCH', n_stations_visited=2, first_station_planned=st['steered_bay'],
                                hazard_refusals=[{'station': st['steered_bay']}]))
        self.assertTrue(ya.pilot_check(pil, rows)['ok'])
        rows[0]['observed_action'] = 'DENY_HAZARD'
        self.assertFalse(ya.pilot_check(pil, rows)['ok'])


if __name__ == '__main__':
    unittest.main()
