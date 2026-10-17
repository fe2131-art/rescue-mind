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
