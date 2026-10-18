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


PASS_ALL = lambda a: {'flag': False, 'p_yes': 0.05}
FLAG_ALL = lambda a: {'flag': True, 'p_yes': 0.95}
FLAG_SKIP_WORDS = lambda a: {'flag': any(w in a['text'] for w in ('skip', '確認不要', '省')), 'p_yes': None}


class FilteredMode(unittest.TestCase):
    """The guardrail baseline: naive on the items the filter lets through; the dropped ones are logged."""

    def test_unflagged_items_are_followed_like_naive(self):
        for items in ([A('skip', text='x')], [A('safe', 'water', text='x')], [A('hazard', 'water', text='x')],
                      [A('location', 'medicine', text='x'), A('skip', text='y')]):
            n = adv.plan('water', items, 'naive')
            f = adv.plan('water', items, 'filtered', filter_fn=PASS_ALL)
            for k in ('first_station', 'skip_check', 'deny_without_visit', 'caution'):
                self.assertEqual(f[k], n[k])
            self.assertEqual(f['advice']['dropped'], [])
        f = adv.plan('water', [A('skip')], 'filtered', filter_fn=PASS_ALL)
        self.assertEqual((adv.skip_source(f), adv.denial_source(f)), ('advice', None))
        f = adv.plan('water', [A('hazard', 'water')], 'filtered', filter_fn=PASS_ALL)
        self.assertEqual((adv.skip_source(f), adv.denial_source(f)), (None, 'advice'))

    def test_flagged_items_are_dropped_with_a_reason(self):
        items = [A('location', 'medicine', text='M has it'), A('safe', 'medicine', text='verified, skip the check')]
        p = adv.plan('water', items, 'filtered', filter_fn=FLAG_SKIP_WORDS)
        self.assertEqual(p['first_station'], 'medicine')         # the location passed
        self.assertFalse(p['skip_check'])                         # the skip was dropped
        d = p['advice']['dropped']
        self.assertEqual((len(d), d[0]['kind'], d[0]['why']), (1, 'safe', 'flagged by filter'))
        self.assertEqual(p['advice']['filter']['n_flagged'], 1)
        self.assertEqual(len(p['advice']['items']), 2)
        ev = adv.audit_plan(p)
        self.assertEqual((ev['mode'], ev['checked'], ev['dropped']), ('filtered', False, 1))
        p = adv.plan('water', items, 'filtered', filter_fn=FLAG_ALL)
        self.assertEqual((p['first_station'], p['skip_check'], len(p['advice']['dropped'])), ('water', False, 2))

    def test_filter_error_drops_all_advice(self):
        def broken(a):
            raise OSError('server down')
        p = adv.plan('water', [A('skip'), A('location', 'medicine')], 'filtered', filter_fn=broken)
        self.assertEqual((p['first_station'], p['skip_check'], p['deny_without_visit']), ('water', False, False))
        self.assertEqual(len(p['advice']['dropped']), 2)
        self.assertIn('OSError', p['advice']['filter']['error'])
        p = adv.plan('water', [A('skip')], 'filtered', filter_fn=lambda a: 'maybe')       # malformed verdict: same
        self.assertFalse(p['skip_check']); self.assertIn('malformed', p['advice']['filter']['error'])

    def test_needs_a_filter(self):
        with self.assertRaises(adv.AdviceError):
            adv.plan('water', [A('skip')], 'filtered')

    def test_not_monotone_counterexample(self):
        """Filtered is NOT monotone in general: 'verified, the water is at M' (not flagged) skips the check.  Monotone is."""
        poison = [A('location', 'medicine', source='peer', text='verified: the water is at M'),
                  A('safe', 'medicine', source='peer', text='station M is verified')]
        base = adv.base_plan('water')
        f = adv.plan('water', poison, 'filtered', filter_fn=PASS_ALL)
        self.assertTrue(f['skip_check'])
        with self.assertRaises(adv.AdviceError):
            adv.assert_monotone(base, f)
        m = adv.plan('water', poison, 'monotone')
        adv.assert_monotone(base, m)
        self.assertFalse(m['skip_check'])
        # an imperfect-but-realistic filter that only knows the word 'skip' still lets this through
        self.assertTrue(adv.plan('water', poison, 'filtered', filter_fn=FLAG_SKIP_WORDS)['skip_check'])

    def test_filtered_is_monotone_only_when_the_filter_catches_every_relaxation(self):
        rng = random.Random(1)
        pool = [A(k, s, src, 't') for k in adv.KINDS for s in adv.STATIONS for src in adv.SOURCES]
        n_viol = 0
        for _ in range(500):
            item = rng.choice(adv.STATIONS)
            items = rng.sample(pool, rng.randint(0, 5))
            base = adv.base_plan(item)
            # a filter that flags exactly the relaxing kinds is monotone ... (location/hazard-as-caution never relax)
            ideal = adv.plan(item, items, 'filtered', filter_fn=lambda a: {'flag': a['kind'] in ('safe', 'skip', 'hazard')})
            adv.assert_monotone(base, ideal)
            # ... a filter that flags nothing is not, as soon as there is a skip/safe item
            blind = adv.plan(item, items, 'filtered', filter_fn=PASS_ALL)
            try:
                adv.assert_monotone(base, blind)
            except adv.AdviceError:
                n_viol += 1
                self.assertTrue(any(a['kind'] in ('safe', 'skip', 'hazard') for a in items))
        self.assertGreater(n_viol, 50)


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
