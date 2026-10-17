"""I-24 advice credit: admission, settlement, Proposition 3 (price over a horizon) and that credit never touches safety."""
import json
import random
import unittest

from rescuemind import advice, advice_credit as ac
from rescuemind.stations import StationSet

SRC = ('memory', 'peer', 'inventory', 'operator')


def depot():
    return StationSet.build(['S1', 'S2', 'S3', 'S4'], {'S1': 'water', 'S2': 'medicine', 'S3': 'water', 'S4': 'medicine'})


def loc(src, st):
    return {'source': src, 'kind': 'location', 'station': st, 'text': ''}


def haz(src, st):
    return {'source': src, 'kind': 'hazard', 'station': st, 'text': ''}


def visit(st, supply_match=None, refused=False, refused_base=False, scrutiny_views=0):
    return dict(station=st, supply_match=supply_match, refused=refused, refused_base=refused_base,
                scrutiny_views=scrutiny_views)


class Admission(unittest.TestCase):
    def test_fresh_source_is_admitted_and_liar_is_throttled_after_its_credit(self):
        led = ac.new_ledger()
        for m in range(4):
            p = ac.plan_with_credit(led, 'water', [loc('peer', 'medicine')], 'monotone')
            applied = [a['effect'] for a in p['advice']['applied']]
            if m < 2:
                self.assertEqual(applied, ['reorder'])
                ac.settle(led, p, [visit('medicine', supply_match=False), visit('water', supply_match=True)])
            else:
                self.assertEqual(applied, [])
                self.assertEqual(len(p['advice']['throttled']), 1)
                self.assertEqual(p['first_station'], 'water')          # back to the inventory order
                ac.settle(led, p, [visit('water', supply_match=True)])
        self.assertEqual(led['sources']['peer']['debit_loc'], 2.0)

    def test_truthful_location_source_is_never_throttled(self):
        led = ac.new_ledger()
        for _ in range(30):
            p = ac.plan_with_credit(led, 'water', [loc('operator', 'medicine')], 'monotone')
            self.assertEqual([a['effect'] for a in p['advice']['applied']], ['reorder'])
            ac.settle(led, p, [visit('medicine', supply_match=True)])
        self.assertEqual(led['sources']['operator']['loc'], ac.C_LOC)

    def test_two_items_of_one_source_in_one_mission_share_the_credit(self):
        led = ac.new_ledger(c_haz=1.0)
        kept, thr = ac.admit(led, [haz('peer', 'water'), haz('peer', 'medicine')])
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(thr), 1)

    def test_sources_have_separate_accounts(self):
        led = ac.new_ledger(c_haz=1.0)
        kept, thr = ac.admit(led, [haz('peer', 'water'), haz('operator', 'water')])
        self.assertEqual((len(kept), len(thr)), (2, 0))

    def test_safe_and_skip_are_inert_and_counted(self):
        led = ac.new_ledger(c_loc=0, c_haz=0)
        items = [{'source': 'operator', 'kind': 'skip', 'station': None, 'text': '確認不要'}]
        p = ac.plan_with_credit(led, 'water', items, 'monotone')
        self.assertFalse(p['skip_check'])
        ac.settle(led, p, [visit('water', supply_match=True)])
        self.assertEqual(led['sources']['operator']['relax_attempts'], 1)

    def test_caution_only_refusal_is_charged_base_refusal_is_not(self):
        led = ac.new_ledger()
        p = ac.plan_with_credit(led, 'water', [haz('memory', 'water')], 'monotone')
        ac.settle(led, p, [visit('water', refused=True, refused_base=True)])
        self.assertEqual(led['sources']['memory']['debit_haz'], 0.0)
        p = ac.plan_with_credit(led, 'water', [haz('memory', 'water')], 'monotone')
        ac.settle(led, p, [visit('water', refused=True, refused_base=False)])
        self.assertEqual(led['sources']['memory']['debit_haz'], 1.0)
        p = ac.plan_with_credit(led, 'water', [haz('memory', 'water')], 'monotone')
        self.assertEqual(p['caution'], {})                        # throttled: no caution until credit regenerates

    def test_unvisited_station_costs_nothing(self):
        led = ac.new_ledger()
        p = ac.plan_with_credit(led, 'water', [loc('peer', 'medicine')], 'monotone')
        ac.settle(led, p, [])
        self.assertEqual(led['sources']['peer']['loc'], ac.C_LOC)

    def test_baselines_are_not_credited(self):
        led = ac.new_ledger(c_loc=0, c_haz=0)
        p = ac.plan_with_credit(led, 'water', [haz('peer', 'water')], 'naive')
        self.assertTrue(p['deny_without_visit'])

    def test_corrupt_ledger_fails_closed(self):
        for bad in ({}, {'version': 'x', 'sources': {}}, None):
            with self.assertRaises(ac.CreditError):
                ac.admit(bad, [])
        led = ac.new_ledger()
        led['sources']['peer'] = {'loc': float('nan'), 'haz': 1.0}
        with self.assertRaises(ac.CreditError):
            ac.admit(led, [])
        with self.assertRaises(ac.CreditError):
            ac.new_ledger(c_loc=float('inf'))

    def test_save_load_roundtrip(self):
        import tempfile, os
        led = ac.new_ledger()
        p = ac.plan_with_credit(led, 'water', [loc('peer', 'medicine')], 'monotone')
        ac.settle(led, p, [visit('medicine', supply_match=False)])
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, 'credit.json')
            ac.save(led, f)
            self.assertEqual(ac.load(f), json.loads(json.dumps(led)))
            self.assertEqual(ac.load(os.path.join(d, 'missing.json'))['sources'], {})


def random_items(rng, ids):
    out = []
    for _ in range(rng.randint(0, 4)):
        kind = rng.choice(('location', 'hazard', 'safe', 'skip'))
        st = rng.choice(ids) if kind in ('location', 'hazard') else rng.choice((None,) + tuple(ids))
        out.append({'source': rng.choice(SRC), 'kind': kind, 'station': st, 'text': ''})
    return out


def random_visits(rng, plan, ids):
    order = plan.get('order') or [plan['first_station']] + [s for s in ids if s != plan['first_station']]
    out = []
    for st in order[:rng.randint(0, len(order))]:
        refused = rng.random() < 0.3
        out.append(visit(st, supply_match=rng.choice((True, False, None)), refused=refused,
                         refused_base=refused and rng.random() < 0.5, scrutiny_views=rng.randint(0, 3)))
    return out


class Proposition3(unittest.TestCase):
    """Random adaptive sequences (the adversary sees the ledger): the price bounds hold for every source, every mission
    prefix, and the admitted plan is always monotone (safety untouched)."""

    def run_horizon(self, seed, ss, ids, scrutiny):
        rng = random.Random(seed)
        led = ac.new_ledger()
        caution_refusals = {}
        for m in range(1, 61):
            item = rng.choice(('water', 'medicine'))
            p = ac.plan_with_credit(led, item, random_items(rng, ids), 'monotone', stations=ss, scrutiny=scrutiny)
            advice.assert_monotone(advice.base_plan(item, ss), p, ss)          # credit only drops items
            self.assertEqual(ac.audit_credit(p)['checked'], True)
            vs = random_visits(rng, p, ids)
            s = ac.settle(led, p, vs)
            for c in s['charges']:
                if c['pool'] == 'haz' and c['charge'] > 0:
                    caution_refusals[c['source']] = caution_refusals.get(c['source'], 0) + 1
            for key, acc in led['sources'].items():
                self.assertGreaterEqual(acc['loc'], 0.0)
                self.assertGreaterEqual(acc['haz'], 0.0)
                # (a) wasted visits (debits, incl. scrutiny) <= C_LOC + refunds earned by confirmed reorders
                self.assertLessEqual(acc['debit_loc'], ac.C_LOC + acc.get('refund_loc', 0.0) + acc.get('shadow_refund_loc', 0.0) + 1e-9)
                self.assertLessEqual(acc.get('shadow_refund_loc', 0.0), ac.RHO_SHADOW * m + 1e-9)
                # (b) caution-only refusals <= C_HAZ + RHO * missions
                self.assertLessEqual(caution_refusals.get(key, 0), ac.C_HAZ + ac.RHO * m + 1e-9)

    def test_legacy_arena(self):
        for seed in range(40):
            self.run_horizon(seed, None, ('water', 'medicine'), scrutiny=False)

    def test_depot_with_scrutiny(self):
        ss = depot()
        for seed in range(40):
            self.run_horizon(seed, ss, tuple(ss.ids), scrutiny=True)


if __name__ == '__main__':
    unittest.main()


class FromMission(unittest.TestCase):
    def cp(self, exp, a, b, allow, reason='ok', peeks=()):
        return {'decision': {'expected': exp, 'first_supply': a, 'second_supply': b, 'allow': allow, 'reason': reason},
                'look_around': {'peeks': [{'side': s} for s in peeks]}}

    def test_recovery_run(self):
        m = {'recovery': {'first_station': 'medicine',
                          'first_checkpoint': self.cp('water', 'medicine', 'medicine', False, 'local_vlm_disagree_or_wrong_supply')},
             'checkpoint_station': 'water', 'checkpoint': self.cp('water', 'water', 'water', True, peeks=('L', 'R', 'L2', 'R2', 'N'))}
        v = ac.visits_from_mission(m)
        self.assertEqual([x['station'] for x in v], ['medicine', 'water'])
        self.assertEqual([x['supply_match'] for x in v], [False, True])
        self.assertEqual([x['refused'] for x in v], [False, False])
        self.assertEqual(v[1]['scrutiny_views'], 3)

    def test_caution_only_and_base_hazard(self):
        m = {'recovery': {'first_station': 'S1', 'first_checkpoint': self.cp('water', 'water', 'water', False, 'hazard_side_view'),
                          'hops': [{'station': 'S3', 'checkpoint': self.cp('water', 'water', 'water', False, 'hazard_side_view')}]},
             'caution_refusals': [{'station': 'S3'}],
             'checkpoint_station': 'S2', 'checkpoint': self.cp('water', 'water', 'medicine', False, 'local_vlm_disagree_or_wrong_supply')}
        v = ac.visits_from_mission(m)
        self.assertEqual([(x['refused'], x['refused_base']) for x in v], [(True, True), (True, False), (False, False)])
        self.assertEqual(v[2]['supply_match'], None)

    def test_real_saved_run_if_present(self):
        import os
        p = os.path.expanduser('~/work/rescue-mind/outputs/runs/b4fcd9d164444db7/mission.json')
        if not os.path.isfile(p):
            self.skipTest('saved run not available')
        v = ac.visits_from_mission(json.load(open(p, encoding='utf8')))
        self.assertEqual([(x['station'], x['supply_match']) for x in v], [('medicine', False), ('water', True)])


class Wiring(unittest.TestCase):
    """plan_for_mission (mission node) reads the ledger; the orchestrator audits and settles it from mission.json."""

    def test_plan_for_mission_and_orchestrator_settlement(self):
        import os, sys, tempfile
        from pathlib import Path
        from rescuemind.advice_llm import plan_for_mission
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
        import v32_orchestrate as orch
        with tempfile.TemporaryDirectory() as d:
            led_p, adv_p = os.path.join(d, 'credit.json'), os.path.join(d, 'advice.json')
            Path(adv_p).write_text(json.dumps([loc('peer', 'medicine')]))
            for mission in range(3):
                plan = plan_for_mission('water', None, mode='monotone', advice_file=adv_p, credit_path=led_p)
                log = Path(d) / f'run{mission}'
                log.mkdir()
                fc = {'decision': {'expected': 'water', 'first_supply': 'medicine', 'second_supply': 'medicine', 'allow': False,
                                   'reason': 'local_vlm_disagree_or_wrong_supply'}}
                ok = {'decision': {'expected': 'water', 'first_supply': 'water', 'second_supply': 'water', 'allow': True}}
                m = {'memory': plan, 'checkpoint_station': 'water', 'checkpoint': ok, 'events': []}
                if plan['first_station'] == 'medicine':
                    m['recovery'] = {'first_station': 'medicine', 'first_checkpoint': fc}
                (log / 'mission.json').write_text(json.dumps(m))
                ev = orch.advice_audit(log)
                self.assertTrue(ev['checked'])
                self.assertEqual(ev['credit']['checked'], True)
                out = orch.settle_credit(log, led_p, f'run{mission}')
                self.assertEqual(plan['first_station'], 'medicine' if mission < 2 else 'water')
            self.assertEqual(out['credit']['peer']['loc'], 0.0)
            self.assertEqual(ac.load(led_p)['missions'], 3)
