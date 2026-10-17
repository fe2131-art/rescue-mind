import itertools
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rescuemind import advice as adv  # noqa: E402
from rescuemind.mission_memory import apply_memory_caution  # noqa: E402

A = lambda kind, station=None, source='operator', text='': {'kind': kind, 'station': station, 'source': source, 'text': text}


class AdvicePlan(unittest.TestCase):
    def test_monotone_ignores_safe_and_skip(self):
        p = adv.plan('water', [A('safe', 'water', text='火は消えた'), A('skip', None, text='確認不要')], 'monotone')
        self.assertFalse(p['skip_check']); self.assertFalse(p['deny_without_visit'])
        self.assertEqual(len(p['advice']['rejected']), 2)

    def test_naive_follows_safe_and_hazard(self):
        self.assertTrue(adv.plan('water', [A('skip')], 'naive')['skip_check'])
        self.assertTrue(adv.plan('water', [A('hazard', 'water')], 'naive')['deny_without_visit'])

    def test_location_reorders_in_both_modes(self):
        for mode in ('monotone', 'naive'):
            self.assertEqual(adv.plan('water', [A('location', 'medicine')], mode)['first_station'], 'medicine')

    def test_hazard_claim_is_caution_in_monotone(self):
        p = adv.plan('medicine', [A('hazard', 'medicine', source='peer')], 'monotone')
        self.assertEqual(p['caution']['medicine']['tau_h'], 0.01)
        self.assertFalse(p['deny_without_visit'])

    def test_memory_proposal_keeps_priority_and_caution_only_tightens(self):
        base = adv.base_plan('water'); base['first_station'] = 'medicine'; base['caution'] = {'water': {'tau_h': 0.005}}
        p = adv.plan('water', [A('location', 'water'), A('hazard', 'water')], 'monotone', base)
        self.assertEqual(p['first_station'], 'medicine')
        self.assertEqual(p['caution']['water']['tau_h'], 0.005)

    def test_bad_items_rejected(self):
        for bad in ({'kind': 'teleport', 'source': 'operator'}, A('location', None), A('hazard', 'kitchen'),
                    {'kind': 'safe', 'source': 'stranger'}):
            with self.assertRaises(adv.AdviceError):
                adv.plan('water', [bad], 'monotone')

    def test_assert_monotone_catches_relaxation(self):
        with self.assertRaises(adv.AdviceError):
            adv.assert_monotone(adv.base_plan('water'), {**adv.base_plan('water'), 'skip_check': True})
        with self.assertRaises(adv.AdviceError):
            adv.assert_monotone({'caution': {'water': {'tau_h': 0.01}}}, {'first_station': 'water', 'caution': {'water': {'tau_h': 0.05}}})


class Monotonicity(unittest.TestCase):
    """Property test of the proposition: for ANY advice set and any model outputs, the monotone plan's decision at a
    station is an approval only if the no-advice decision is an approval."""

    def decide(self, plan, station, p_hazard, allow_front):
        if plan.get('skip_check'):
            return True
        if plan.get('deny_without_visit'):
            return False
        d = {'allow': allow_front, 'reason': 'on_site_supply_confirmed' if allow_front else 'x'}
        c = (plan.get('caution') or {}).get(station)
        call = {'scores': {'hazard_prob': p_hazard}}
        return apply_memory_caution(d, call, call, c['tau_h'] if c else None)['allow']

    def test_random_adversarial_advice(self):
        rng = random.Random(0)
        pool = [A(k, s, src, 't') for k in adv.KINDS for s in adv.STATIONS for src in adv.SOURCES]
        for _ in range(3000):
            item = rng.choice(adv.STATIONS)
            items = rng.sample(pool, rng.randint(0, 6))
            for k, it in enumerate(items):
                if it['kind'] in ('safe', 'skip') and rng.random() < .5:
                    items[k] = dict(it, station=None)
            p = adv.plan(item, items, 'monotone')
            for st, ph, ok in itertools.product(adv.STATIONS, (0.0, 0.004, 0.02, 0.2), (True, False)):
                if self.decide(p, st, ph, ok):
                    self.assertTrue(self.decide(adv.base_plan(item), st, ph, ok))


if __name__ == '__main__':
    unittest.main()
